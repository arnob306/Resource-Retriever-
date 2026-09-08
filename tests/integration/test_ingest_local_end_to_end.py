from resource_retriever.indexing.ingest_service import run_ingest
from resource_retriever.storage.sqlite_metadata_store import SqliteMetadataStore


def test_ingest_populates_metadata_for_all_sample_pdfs(tmp_data_dir, app_config, sample_pdfs_dir):
    store = SqliteMetadataStore(tmp_data_dir / "metadata.sqlite3")

    summary = run_ingest(sample_pdfs_dir, store, app_config)

    expected_count = len(list(sample_pdfs_dir.glob("*.pdf")))
    assert summary.discovered == expected_count
    assert summary.new == expected_count
    assert summary.failed == 0

    for pdf_path in sample_pdfs_dir.glob("*.pdf"):
        record = store.get_by_path(str(pdf_path.resolve()))
        assert record is not None
        assert record.content_hash is not None
        assert record.page_count is not None and record.page_count >= 1
        assert record.status == "discovered"

    store.close()


def test_rerunning_ingest_with_no_changes_reports_unchanged(tmp_data_dir, app_config, sample_pdfs_dir):
    store = SqliteMetadataStore(tmp_data_dir / "metadata.sqlite3")

    run_ingest(sample_pdfs_dir, store, app_config)
    summary = run_ingest(sample_pdfs_dir, store, app_config)

    expected_count = len(list(sample_pdfs_dir.glob("*.pdf")))
    assert summary.new == 0
    assert summary.unchanged == expected_count

    store.close()
