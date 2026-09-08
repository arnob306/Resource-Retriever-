from resource_retriever.models.chunk import Chunk
from resource_retriever.storage.chroma_vector_store import ChromaVectorStore


def _chunk(file_id: str, chunk_index: int, text: str) -> Chunk:
    return Chunk(
        file_id=file_id,
        chunk_index=chunk_index,
        text=text,
        page_start=1,
        page_end=1,
        char_start=0,
        char_end=len(text),
    )


def test_upsert_then_query_returns_the_upserted_chunk(tmp_path):
    # Arrange
    store = ChromaVectorStore(tmp_path / "chroma")
    chunk = _chunk("file-1", 0, "quadratic word problems for year nine")

    # Act
    store.upsert_chunks([chunk], [[1.0, 0.0, 0.0]], content_hash="hash-1")
    results = store.query([1.0, 0.0, 0.0], top_k=5)

    # Assert
    assert len(results) == 1
    assert results[0].file_id == "file-1"
    assert results[0].text == chunk.text
    assert results[0].content_hash == "hash-1"


def test_has_file_hash_true_only_for_matching_pair(tmp_path):
    # Arrange
    store = ChromaVectorStore(tmp_path / "chroma")
    store.upsert_chunks([_chunk("file-1", 0, "text")], [[1.0, 0.0, 0.0]], content_hash="hash-1")

    # Act / Assert
    assert store.has_file_hash("file-1", "hash-1") is True
    assert store.has_file_hash("file-1", "hash-2") is False
    assert store.has_file_hash("file-2", "hash-1") is False


def test_delete_by_file_id_removes_only_that_files_chunks(tmp_path):
    # Arrange
    store = ChromaVectorStore(tmp_path / "chroma")
    store.upsert_chunks([_chunk("file-1", 0, "keep me")], [[1.0, 0.0, 0.0]], content_hash="hash-1")
    store.upsert_chunks([_chunk("file-2", 0, "delete me")], [[0.0, 1.0, 0.0]], content_hash="hash-2")

    # Act
    store.delete_by_file_id("file-2")

    # Assert
    assert store.has_file_hash("file-1", "hash-1") is True
    assert store.has_file_hash("file-2", "hash-2") is False


def test_upsert_overwrites_rather_than_duplicates_on_same_ids(tmp_path):
    # Arrange
    store = ChromaVectorStore(tmp_path / "chroma")
    chunk = _chunk("file-1", 0, "original text")

    # Act — re-embed the same file/chunk_index with new content
    store.upsert_chunks([chunk], [[1.0, 0.0, 0.0]], content_hash="hash-1")
    updated_chunk = _chunk("file-1", 0, "updated text")
    store.upsert_chunks([updated_chunk], [[1.0, 0.0, 0.0]], content_hash="hash-2")
    results = store.query([1.0, 0.0, 0.0], top_k=10)

    # Assert
    assert len(results) == 1
    assert results[0].text == "updated text"
