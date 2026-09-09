from resource_retriever.models.file_record import FileRecord
from resource_retriever.search.search_service import find
from resource_retriever.storage.vector_store import VectorMatch, VectorStore


def _record(**overrides) -> FileRecord:
    base = dict(
        id="file-1",
        source_type="local",
        local_path="/docs/worksheet.pdf",
        drive_id=None,
        display_name="worksheet.pdf",
        content_hash="hash-a",
        file_size=1024,
        modified_time=1_700_000_000_000,
        page_count=2,
        status="indexed",
        indexed_at="2024-01-01T00:00:00+00:00",
        created_at="2024-01-01T00:00:00+00:00",
    )
    base.update(overrides)
    return FileRecord(**base)


def _match(file_id: str, chunk_index: int, score: float, content_hash: str, text: str = "some chunk text") -> VectorMatch:
    return VectorMatch(
        file_id=file_id,
        chunk_index=chunk_index,
        text=text,
        page_start=1,
        page_end=1,
        content_hash=content_hash,
        score=score,
    )


class FakeVectorStore(VectorStore):
    """Ignores the embedding entirely and returns a canned, pre-sorted list of matches."""

    def __init__(self, matches: list[VectorMatch]):
        self._matches = matches

    def upsert_chunks(self, chunks, embeddings, content_hash):
        raise NotImplementedError

    def delete_by_file_id(self, file_id):
        raise NotImplementedError

    def has_file_hash(self, file_id, content_hash):
        raise NotImplementedError

    def query(self, embedding, top_k):
        return self._matches[:top_k]


class FakeEmbedder:
    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def test_closer_match_ranks_before_farther_match(metadata_store):
    # Arrange
    metadata_store.upsert_file(_record(id="file-a", local_path="/docs/a.pdf", content_hash="hash-a"))
    metadata_store.upsert_file(_record(id="file-b", local_path="/docs/b.pdf", content_hash="hash-b"))
    matches = [_match("file-a", 0, score=0.91, content_hash="hash-a"), _match("file-b", 0, score=0.42, content_hash="hash-b")]
    vector_store = FakeVectorStore(matches)

    # Act
    outcome = find("quadratic word problems", metadata_store, vector_store, FakeEmbedder(), top_k=5)

    # Assert
    assert [r.file_path for r in outcome.results] == ["/docs/a.pdf", "/docs/b.pdf"]
    assert outcome.results[0].score > outcome.results[1].score


def test_duplicate_content_hash_is_deduped_keeping_first_seen(metadata_store):
    # Arrange — two different files, same content_hash (a copy in two locations)
    metadata_store.upsert_file(_record(id="file-a", local_path="/drive-mirror/a.pdf", content_hash="hash-shared"))
    metadata_store.upsert_file(_record(id="file-b", local_path="/downloads/a-copy.pdf", content_hash="hash-shared"))
    matches = [
        _match("file-a", 0, score=0.9, content_hash="hash-shared"),
        _match("file-b", 0, score=0.8, content_hash="hash-shared"),
    ]
    vector_store = FakeVectorStore(matches)

    # Act
    outcome = find("quadratic word problems", metadata_store, vector_store, FakeEmbedder(), top_k=5)

    # Assert
    assert len(outcome.results) == 1
    assert outcome.results[0].file_path == "/drive-mirror/a.pdf"


def test_result_missing_from_metadata_store_is_skipped_not_crashed(metadata_store):
    # Arrange — a vector match whose file_id was never indexed into SQLite (deleted since embedding)
    vector_store = FakeVectorStore([_match("ghost-file", 0, score=0.99, content_hash="hash-x")])

    # Act
    outcome = find("anything", metadata_store, vector_store, FakeEmbedder(), top_k=5)

    # Assert
    assert outcome.results == []


def test_find_logs_latency_and_result_count_to_search_log(metadata_store):
    # Arrange
    metadata_store.upsert_file(_record())
    vector_store = FakeVectorStore([_match("file-1", 0, score=0.5, content_hash="hash-a")])

    # Act
    outcome = find("quadratics", metadata_store, vector_store, FakeEmbedder(), top_k=5)

    # Assert
    assert outcome.latency_ms >= 0
    row = metadata_store._connection.execute("SELECT query, result_count FROM search_log").fetchone()
    assert row["query"] == "quadratics"
    assert row["result_count"] == 1
