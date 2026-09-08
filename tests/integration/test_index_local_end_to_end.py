"""End-to-end Phase 2 check: ingest -> index against the real sample PDFs, real embedder, real Chroma.

Downloads the sentence-transformers model on first run (network required once); subsequent runs
use the local HF cache. This is intentionally slower than the unit tests — it is the one place we
verify the chunker + embedder + vector store actually agree with each other in practice.
"""

from pathlib import Path

import pytest

from resource_retriever.config import AppConfig
from resource_retriever.embedding.embedder import Embedder
from resource_retriever.indexing.index_service import run_index
from resource_retriever.indexing.ingest_service import run_ingest
from resource_retriever.storage.chroma_vector_store import ChromaVectorStore
from resource_retriever.storage.sqlite_metadata_store import SqliteMetadataStore

pytestmark = pytest.mark.integration

_SAMPLE_PDFS_DIR = Path(__file__).resolve().parent.parent.parent / "sample_pdfs"


@pytest.fixture(scope="module")
def indexed_environment(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("phase2_data")
    app_config = AppConfig(data_dir=data_dir)
    store = SqliteMetadataStore(app_config.metadata_db_path)
    run_ingest(_SAMPLE_PDFS_DIR, store, app_config)

    vector_store = ChromaVectorStore(app_config.chroma_dir)
    embedder = Embedder(app_config)
    first_summary = run_index(store, vector_store, embedder, app_config)

    yield app_config, store, vector_store, embedder, first_summary
    store.close()


def test_index_embeds_every_ingested_file(indexed_environment):
    # Arrange
    app_config, store, vector_store, embedder, summary = indexed_environment
    records = store.list_all(source_type="local")

    # Assert
    assert summary.failed == 0
    assert all(record.status == "indexed" for record in records)
    assert summary.new == len(records)


def test_no_chunk_exceeds_the_configured_window_when_retokenized(indexed_environment):
    # Arrange
    app_config, store, vector_store, embedder, summary = indexed_environment
    records = store.list_all(source_type="local")

    # Act / Assert — pull every chunk back out of Chroma via a broad self-query and retokenize it
    for record in records:
        query_vector = embedder.embed_query(record.display_name)
        matches = vector_store.query(query_vector, top_k=50)
        file_matches = [m for m in matches if m.file_id == record.id]
        assert file_matches, f"expected at least one chunk for {record.display_name}"
        for match in file_matches:
            token_count = len(embedder.tokenizer(match.text, add_special_tokens=False)["input_ids"])
            assert token_count <= app_config.chunk_window_tokens


def test_chunk_metadata_has_valid_page_ranges(indexed_environment):
    # Arrange
    app_config, store, vector_store, embedder, summary = indexed_environment
    records = store.list_all(source_type="local")
    record = records[0]

    # Act
    query_vector = embedder.embed_query(record.display_name)
    matches = [m for m in vector_store.query(query_vector, top_k=50) if m.file_id == record.id]

    # Assert
    for match in matches:
        assert match.page_start >= 1
        assert match.page_end >= match.page_start
        assert match.page_end <= record.page_count


def test_rerunning_index_with_no_changes_reprocesses_nothing(indexed_environment):
    # Arrange
    app_config, store, vector_store, embedder, _first_summary = indexed_environment

    # Act
    second_summary = run_index(store, vector_store, embedder, app_config)

    # Assert
    assert second_summary.new == 0
    assert second_summary.reprocessed == 0
    assert second_summary.failed == 0
