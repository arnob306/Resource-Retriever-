"""Phase 5 check: a full ingest -> index -> ingest -> index cycle over the real sample corpus
must not force a needless re-embed the second time through, and a single genuinely modified file
must trigger exactly one re-embed — the incremental-reindex-at-scale contract Phase 5 exists to
guarantee. Uses the real embedder and a real Chroma store, same tradeoff as the other Phase 2/3
integration tests: slower, but the one place that proves the whole pipeline agrees with itself.
"""

import os
import shutil
import time

import pytest

from resource_retriever.config import AppConfig
from resource_retriever.embedding.embedder import Embedder
from resource_retriever.indexing.index_service import run_index
from resource_retriever.indexing.ingest_service import run_ingest
from resource_retriever.storage.chroma_vector_store import ChromaVectorStore
from resource_retriever.storage.sqlite_metadata_store import SqliteMetadataStore

pytestmark = pytest.mark.integration


def test_rerunning_ingest_and_index_with_no_changes_reprocesses_nothing(tmp_path_factory, sample_pdfs_dir):
    # Arrange
    data_dir = tmp_path_factory.mktemp("phase5_noop")
    app_config = AppConfig(data_dir=data_dir)
    store = SqliteMetadataStore(app_config.metadata_db_path)
    vector_store = ChromaVectorStore(app_config.chroma_dir)
    embedder = Embedder(app_config)
    run_ingest(sample_pdfs_dir, store, app_config)
    first_index = run_index(store, vector_store, embedder, app_config)
    assert first_index.failed == 0

    # Act — the realistic "did anything change?" workflow: ingest again, then index again
    run_ingest(sample_pdfs_dir, store, app_config)
    second_index = run_index(store, vector_store, embedder, app_config)

    # Assert — nothing changed, so nothing should be re-embedded
    assert second_index.new == 0
    assert second_index.reprocessed == 0
    assert second_index.failed == 0

    store.close()


def test_modifying_one_file_triggers_exactly_one_reembed(tmp_path_factory, tmp_path, sample_pdfs_dir):
    # Arrange — a private, writable copy of the sample corpus
    corpus = tmp_path / "corpus"
    shutil.copytree(sample_pdfs_dir, corpus)
    data_dir = tmp_path_factory.mktemp("phase5_one_change")
    app_config = AppConfig(data_dir=data_dir)
    store = SqliteMetadataStore(app_config.metadata_db_path)
    vector_store = ChromaVectorStore(app_config.chroma_dir)
    embedder = Embedder(app_config)
    run_ingest(corpus, store, app_config)
    run_index(store, vector_store, embedder, app_config)

    # Act — swap exactly one file's content for a different (still fully valid) sample PDF's
    # bytes, so its content_hash genuinely changes without corrupting the PDF structure, and
    # bump its mtime forward so the cheap pre-check actually re-hashes it.
    pdfs = sorted(corpus.glob("*.pdf"))
    target, donor = pdfs[0], pdfs[1]
    target.write_bytes(donor.read_bytes())
    future = time.time() + 5
    os.utime(target, (future, future))

    run_ingest(corpus, store, app_config)
    summary = run_index(store, vector_store, embedder, app_config)

    # Assert — exactly one file needed re-embedding
    assert summary.new == 0
    assert summary.reprocessed == 1
    assert summary.failed == 0

    store.close()
