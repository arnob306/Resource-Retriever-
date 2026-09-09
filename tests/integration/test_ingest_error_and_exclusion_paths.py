from dataclasses import replace

from resource_retriever.indexing.ingest_service import run_ingest
from resource_retriever.storage.sqlite_metadata_store import SqliteMetadataStore


def test_corrupt_file_is_recorded_as_extraction_failed_not_a_crash(tmp_path, tmp_data_dir, app_config):
    root = tmp_path / "resources"
    root.mkdir()
    corrupt_pdf = root / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"this is not a real pdf file")
    store = SqliteMetadataStore(tmp_data_dir / "metadata.sqlite3")

    summary = run_ingest(root, store, app_config)

    assert summary.discovered == 1
    assert summary.failed == 1
    assert summary.new == 0

    record = store.get_by_path(str(corrupt_pdf.resolve()))
    assert record is not None
    assert record.status == "extraction_failed"
    assert record.content_hash is None
    assert record.page_count is None

    store.close()


def test_excluded_file_is_recorded_as_excluded_without_hashing_or_extraction(tmp_path, tmp_data_dir, app_config):
    root = tmp_path / "resources"
    excluded_folder = root / "student work"
    excluded_folder.mkdir(parents=True)
    excluded_pdf = excluded_folder / "report.pdf"
    excluded_pdf.write_bytes(b"this is not a real pdf file")  # would fail extraction if attempted
    excluding_config = replace(app_config, exclude_folder_names=("student work",))
    store = SqliteMetadataStore(tmp_data_dir / "metadata.sqlite3")

    summary = run_ingest(root, store, excluding_config)

    assert summary.discovered == 1
    assert summary.excluded == 1
    assert summary.failed == 0
    assert summary.new == 0

    record = store.get_by_path(str(excluded_pdf.resolve()))
    assert record is not None
    assert record.status == "excluded"
    assert record.content_hash is None
    assert record.page_count is None

    store.close()
