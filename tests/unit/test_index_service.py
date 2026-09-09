"""Unit-level resilience tests for run_index: a single bad file must never abort the whole run.

Uses fakes/monkeypatches for extraction, chunking, and embedding so these tests run fast and
without a real PDF/tokenizer/model — the real pipeline is exercised by the slow integration test
in tests/integration/test_index_local_end_to_end.py instead.
"""

from pathlib import Path

from resource_retriever.chunking.chunker import ChunkSpan
from resource_retriever.extraction.pdf_text_extractor import PageText
from resource_retriever.indexing import index_service
from resource_retriever.models.file_record import FileRecord
from resource_retriever.storage.vector_store import VectorStore


def _record(**overrides) -> FileRecord:
    base = dict(
        id="file-1",
        source_type="local",
        local_path="dummy.pdf",
        drive_id=None,
        display_name="dummy.pdf",
        content_hash=None,
        file_size=None,
        modified_time=0,
        page_count=None,
        status="discovered",
        indexed_at=None,
        created_at="2024-01-01T00:00:00+00:00",
    )
    base.update(overrides)
    return FileRecord(**base)


class RecordingVectorStore(VectorStore):
    def __init__(self):
        self.upserts = []
        self.deletes = []

    def upsert_chunks(self, chunks, embeddings, content_hash):
        self.upserts.append((chunks, embeddings, content_hash))

    def delete_by_file_id(self, file_id):
        self.deletes.append(file_id)

    def has_file_hash(self, file_id, content_hash):
        return False

    def query(self, embedding, top_k):
        return []


class StubEmbedder:
    """No real model/tokenizer needed — extract_pages/chunk_pages are monkeypatched away."""

    tokenizer = None

    def embed_documents(self, texts):
        return [[0.1, 0.2] for _ in texts]


def _stub_extract_and_chunk(monkeypatch):
    monkeypatch.setattr(index_service, "extract_pages", lambda data: [PageText(page_number=1, text="hello world")])
    monkeypatch.setattr(
        index_service,
        "chunk_pages",
        lambda pages, tokenizer, window, overlap: [
            ChunkSpan(text="hello world", page_start=1, page_end=1, char_start=0, char_end=11)
        ],
    )


def _touch(path: Path) -> tuple[int, int]:
    path.write_bytes(b"stub")
    stat = path.stat()
    return int(stat.st_mtime * 1000), stat.st_size


def test_run_index_marks_one_bad_file_failed_without_aborting_the_run(monkeypatch, metadata_store, app_config, tmp_path):
    # Arrange — two tracked local files; embedding fails for exactly one of them
    _stub_extract_and_chunk(monkeypatch)
    good_path = tmp_path / "good.pdf"
    bad_path = tmp_path / "bad.pdf"
    good_mtime, good_size = _touch(good_path)
    bad_mtime, bad_size = _touch(bad_path)
    metadata_store.upsert_file(
        _record(id="good", local_path=str(good_path), display_name="good.pdf", modified_time=good_mtime, file_size=good_size)
    )
    metadata_store.upsert_file(
        _record(id="bad", local_path=str(bad_path), display_name="bad.pdf", modified_time=bad_mtime, file_size=bad_size)
    )

    class FlakyEmbedder(StubEmbedder):
        def embed_documents(self, texts):
            if any("bad" in text for text in texts):
                raise RuntimeError("simulated embedding backend failure")
            return super().embed_documents(texts)

    vector_store = RecordingVectorStore()

    # Act
    summary = index_service.run_index(metadata_store, vector_store, FlakyEmbedder(), app_config)

    # Assert — the run finishes, the bad file is marked failed, the good file still gets indexed
    assert summary.failed == 1
    assert summary.new == 1
    records = {record.id: record for record in metadata_store.list_all(source_type="local")}
    assert records["bad"].status == "extraction_failed"
    assert records["good"].status == "indexed"
    assert vector_store.deletes == ["good"]
    assert len(vector_store.upserts) == 1


def test_run_index_marks_unreadable_file_failed_without_aborting_the_run(monkeypatch, metadata_store, app_config, tmp_path):
    # Arrange — one normal file, one that raises on read (e.g. a locked/permission-denied file)
    _stub_extract_and_chunk(monkeypatch)
    good_path = tmp_path / "good.pdf"
    locked_path = tmp_path / "locked.pdf"
    good_mtime, good_size = _touch(good_path)
    locked_mtime, locked_size = _touch(locked_path)
    metadata_store.upsert_file(
        _record(id="good", local_path=str(good_path), display_name="good.pdf", modified_time=good_mtime, file_size=good_size)
    )
    metadata_store.upsert_file(
        _record(
            id="locked", local_path=str(locked_path), display_name="locked.pdf", modified_time=locked_mtime, file_size=locked_size
        )
    )

    original_read_bytes = Path.read_bytes

    def flaky_read_bytes(self):
        if self.name == "locked.pdf":
            raise PermissionError("simulated permission error")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", flaky_read_bytes)

    # Act
    summary = index_service.run_index(metadata_store, RecordingVectorStore(), StubEmbedder(), app_config)

    # Assert — the run finishes, the unreadable file is counted failed but left tracked (not purged)
    assert summary.failed == 1
    assert summary.new == 1
    records = {record.id: record for record in metadata_store.list_all(source_type="local")}
    assert records["good"].status == "indexed"
    assert records["locked"].status == "discovered"


def test_run_index_purges_vectors_for_a_file_excluded_after_being_indexed(metadata_store, app_config):
    # Arrange — previously indexed (indexed_at set), then excluded since (e.g. a new denylist rule)
    metadata_store.upsert_file(
        _record(
            id="now-excluded",
            status="excluded",
            content_hash="hash-a",
            indexed_at="2024-01-01T00:00:00+00:00",
        )
    )
    vector_store = RecordingVectorStore()

    # Act
    summary = index_service.run_index(metadata_store, vector_store, StubEmbedder(), app_config)

    # Assert — its stale chunks are purged from the vector store and indexed_at is cleared
    assert vector_store.deletes == ["now-excluded"]
    assert summary.deleted == 1
    record = metadata_store.get_by_id("now-excluded")
    assert record.status == "excluded"
    assert record.indexed_at is None


def test_run_index_leaves_never_indexed_excluded_file_alone(metadata_store, app_config):
    # Arrange — excluded from the start (e.g. at ingest time), never embedded, indexed_at is None
    metadata_store.upsert_file(_record(id="always-excluded", status="excluded", indexed_at=None))
    vector_store = RecordingVectorStore()

    # Act
    summary = index_service.run_index(metadata_store, vector_store, StubEmbedder(), app_config)

    # Assert — nothing to purge, no wasted delete call
    assert vector_store.deletes == []
    assert summary.deleted == 0
