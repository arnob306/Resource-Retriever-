"""Unit tests for drive_index_service.run_drive_index. Extraction/chunking/embedding and the
Drive `service` object are all faked or monkeypatched — no real network calls, no real model.
"""

from unittest.mock import MagicMock

from resource_retriever.chunking.chunker import ChunkSpan
from resource_retriever.config import AppConfig
from resource_retriever.extraction.pdf_text_extractor import PageText
from resource_retriever.indexing import drive_index_service
from resource_retriever.storage.vector_store import VectorStore


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
    tokenizer = None

    def embed_documents(self, texts):
        return [[0.1, 0.2] for _ in texts]


def _stub_extract_and_chunk(monkeypatch):
    monkeypatch.setattr(drive_index_service, "extract_pages", lambda data: [PageText(page_number=1, text="hello world")])
    monkeypatch.setattr(
        drive_index_service,
        "chunk_pages",
        lambda pages, tokenizer, window, overlap: [
            ChunkSpan(text="hello world", page_start=1, page_end=1, char_start=0, char_end=11)
        ],
    )


def _fake_drive_service(entries: list[dict]) -> MagicMock:
    service = MagicMock()
    service.files.return_value.list.return_value.execute.return_value = {"files": entries}
    return service


def _entry(**overrides) -> dict:
    base = dict(
        id="drive-1", name="worksheet.pdf", modifiedTime="2024-01-01T00:00:00.000Z", md5Checksum="hash-a", size="100"
    )
    base.update(overrides)
    return base


def test_run_drive_index_embeds_a_new_file(monkeypatch, metadata_store, app_config):
    _stub_extract_and_chunk(monkeypatch)
    monkeypatch.setattr(drive_index_service, "stream_drive_file_bytes", lambda service, drive_id: b"%PDF-fake%")
    service = _fake_drive_service([_entry()])
    vector_store = RecordingVectorStore()

    summary = drive_index_service.run_drive_index(service, metadata_store, vector_store, StubEmbedder(), app_config)

    assert summary.new == 1
    assert summary.failed == 0
    record = metadata_store.get_by_drive_id("drive-1")
    assert record.status == "indexed"
    assert record.source_type == "drive"
    assert record.local_path is None
    assert record.content_hash == "hash-a"
    assert len(vector_store.upserts) == 1


def test_run_drive_index_skips_unchanged_file_on_second_run(monkeypatch, metadata_store, app_config):
    _stub_extract_and_chunk(monkeypatch)
    download_calls: list[str] = []
    monkeypatch.setattr(
        drive_index_service,
        "stream_drive_file_bytes",
        lambda service, drive_id: (download_calls.append(drive_id), b"%PDF-fake%")[1],
    )
    service = _fake_drive_service([_entry()])
    vector_store = RecordingVectorStore()

    first = drive_index_service.run_drive_index(service, metadata_store, vector_store, StubEmbedder(), app_config)
    second = drive_index_service.run_drive_index(service, metadata_store, vector_store, StubEmbedder(), app_config)

    assert first.new == 1
    assert second.new == 0
    assert second.skipped == 1
    assert download_calls == ["drive-1"]  # only the first run downloaded anything


def test_run_drive_index_reprocesses_when_md5_changes(monkeypatch, metadata_store, app_config):
    _stub_extract_and_chunk(monkeypatch)
    monkeypatch.setattr(drive_index_service, "stream_drive_file_bytes", lambda service, drive_id: b"%PDF-fake%")
    vector_store = RecordingVectorStore()

    service_v1 = _fake_drive_service([_entry(md5Checksum="hash-a")])
    drive_index_service.run_drive_index(service_v1, metadata_store, vector_store, StubEmbedder(), app_config)

    service_v2 = _fake_drive_service([_entry(md5Checksum="hash-b", modifiedTime="2024-06-01T00:00:00.000Z")])
    summary = drive_index_service.run_drive_index(service_v2, metadata_store, vector_store, StubEmbedder(), app_config)

    assert summary.reprocessed == 1
    record = metadata_store.get_by_drive_id("drive-1")
    assert record.content_hash == "hash-b"


def test_run_drive_index_purges_vectors_for_file_excluded_after_being_indexed(monkeypatch, metadata_store, app_config):
    _stub_extract_and_chunk(monkeypatch)
    monkeypatch.setattr(drive_index_service, "stream_drive_file_bytes", lambda service, drive_id: b"%PDF-fake%")
    vector_store = RecordingVectorStore()
    service_v1 = _fake_drive_service([_entry(name="worksheet.pdf")])
    drive_index_service.run_drive_index(service_v1, metadata_store, vector_store, StubEmbedder(), app_config)
    record_id = metadata_store.get_by_drive_id("drive-1").id

    excluding_config = AppConfig(data_dir=app_config.data_dir, exclude_path_substrings=("worksheet",))
    service_v2 = _fake_drive_service([_entry(name="worksheet.pdf")])
    summary = drive_index_service.run_drive_index(service_v2, metadata_store, vector_store, StubEmbedder(), excluding_config)

    assert vector_store.deletes[-1] == record_id
    record = metadata_store.get_by_drive_id("drive-1")
    assert record.status == "excluded"
    assert record.indexed_at is None
    assert summary.discovered == 0  # excluded files never count toward "discovered"


def test_run_drive_index_purges_file_removed_from_drive(monkeypatch, metadata_store, app_config):
    _stub_extract_and_chunk(monkeypatch)
    monkeypatch.setattr(drive_index_service, "stream_drive_file_bytes", lambda service, drive_id: b"%PDF-fake%")
    vector_store = RecordingVectorStore()
    service_v1 = _fake_drive_service([_entry()])
    drive_index_service.run_drive_index(service_v1, metadata_store, vector_store, StubEmbedder(), app_config)
    record_id = metadata_store.get_by_drive_id("drive-1").id

    service_v2 = _fake_drive_service([])  # file no longer appears in Drive
    summary = drive_index_service.run_drive_index(service_v2, metadata_store, vector_store, StubEmbedder(), app_config)

    assert summary.deleted == 1
    assert record_id in vector_store.deletes
    assert metadata_store.get_by_drive_id("drive-1") is None


def test_run_drive_index_marks_one_bad_file_failed_without_aborting_the_run(monkeypatch, metadata_store, app_config):
    _stub_extract_and_chunk(monkeypatch)

    def flaky_download(service, drive_id):
        if drive_id == "bad":
            raise RuntimeError("simulated download failure")
        return b"%PDF-fake%"

    monkeypatch.setattr(drive_index_service, "stream_drive_file_bytes", flaky_download)
    service = _fake_drive_service(
        [_entry(id="good", name="good.pdf", md5Checksum="hash-good"), _entry(id="bad", name="bad.pdf", md5Checksum="hash-bad")]
    )
    vector_store = RecordingVectorStore()

    summary = drive_index_service.run_drive_index(service, metadata_store, vector_store, StubEmbedder(), app_config)

    assert summary.failed == 1
    assert summary.new == 1
    assert metadata_store.get_by_drive_id("good").status == "indexed"
    assert metadata_store.get_by_drive_id("bad").status == "extraction_failed"


def test_run_drive_index_skips_file_exceeding_the_size_cap_without_downloading(monkeypatch, metadata_store, app_config):
    _stub_extract_and_chunk(monkeypatch)
    download_calls: list[str] = []
    monkeypatch.setattr(
        drive_index_service,
        "stream_drive_file_bytes",
        lambda service, drive_id: (download_calls.append(drive_id), b"%PDF-fake%")[1],
    )
    oversized = str(drive_index_service._MAX_DOWNLOAD_BYTES + 1)
    service = _fake_drive_service([_entry(size=oversized)])
    vector_store = RecordingVectorStore()

    summary = drive_index_service.run_drive_index(service, metadata_store, vector_store, StubEmbedder(), app_config)

    assert summary.failed == 1
    assert download_calls == []  # never even attempted the download
    assert metadata_store.get_by_drive_id("drive-1").status == "extraction_failed"


def test_run_drive_index_does_not_issue_a_query_per_file(monkeypatch, metadata_store, app_config):
    # Regression: existing records must be bulk-loaded once, not looked up one-by-one per file
    _stub_extract_and_chunk(monkeypatch)
    monkeypatch.setattr(drive_index_service, "stream_drive_file_bytes", lambda service, drive_id: b"%PDF-fake%")
    service = _fake_drive_service([_entry(id="a", md5Checksum="hash-a"), _entry(id="b", md5Checksum="hash-b")])
    vector_store = RecordingVectorStore()

    calls = {"count": 0}
    original_get_by_drive_id = metadata_store.get_by_drive_id

    def counting_get_by_drive_id(drive_id):
        calls["count"] += 1
        return original_get_by_drive_id(drive_id)

    monkeypatch.setattr(metadata_store, "get_by_drive_id", counting_get_by_drive_id)

    drive_index_service.run_drive_index(service, metadata_store, vector_store, StubEmbedder(), app_config)

    assert calls["count"] == 0
