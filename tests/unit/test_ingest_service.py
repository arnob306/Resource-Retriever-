"""Unit tests for ingest_service.py's cheap mtime/size pre-check (Phase 5 optimization).

walk_local_folder is monkeypatched so these tests control exactly what's "discovered" without a
real directory tree; extract_pages is stubbed too since only the pre-check control flow is under
test here, not real PDF parsing (covered by the integration tests).
"""

from pathlib import Path

from resource_retriever.hashing import compute_content_hash
from resource_retriever.indexing import ingest_service
from resource_retriever.ingestion.local_walker import DiscoveredFile
from resource_retriever.models.file_record import FileRecord


def _discovered(path: Path, mtime: int = 1_000, size: int = 10, excluded: bool = False) -> DiscoveredFile:
    return DiscoveredFile(
        local_path=str(path), display_name=path.name, modified_time=mtime, file_size=size, is_excluded=excluded
    )


def _record(**overrides) -> FileRecord:
    base = dict(
        id="file-1",
        source_type="local",
        local_path="dummy.pdf",
        drive_id=None,
        display_name="dummy.pdf",
        content_hash="hash-a",
        file_size=10,
        modified_time=1_000,
        page_count=2,
        status="indexed",
        indexed_at="2024-01-01T00:00:00+00:00",
        created_at="2024-01-01T00:00:00+00:00",
    )
    base.update(overrides)
    return FileRecord(**base)


def _fail(*_args, **_kwargs):
    raise AssertionError("should not have been called for an unchanged file")


def test_skips_read_and_extract_when_mtime_and_size_unchanged(monkeypatch, metadata_store, app_config, tmp_path):
    pdf_path = tmp_path / "worksheet.pdf"
    pdf_path.write_bytes(b"stub")
    metadata_store.upsert_file(
        _record(local_path=str(pdf_path), content_hash="hash-a", file_size=10, modified_time=1_000, status="indexed")
    )
    monkeypatch.setattr(ingest_service, "walk_local_folder", lambda root, config: iter([_discovered(pdf_path)]))
    monkeypatch.setattr(ingest_service, "extract_pages", _fail)
    monkeypatch.setattr(Path, "read_bytes", _fail)

    summary = ingest_service.run_ingest(tmp_path, metadata_store, app_config)

    assert summary.unchanged == 1
    assert summary.new == 0
    assert metadata_store.get_by_path(str(pdf_path)).status == "indexed"


def test_force_rehash_bypasses_the_unchanged_fast_path(monkeypatch, metadata_store, app_config, tmp_path):
    pdf_path = tmp_path / "worksheet.pdf"
    pdf_bytes = b"same-content"
    pdf_path.write_bytes(pdf_bytes)
    real_hash = compute_content_hash(pdf_bytes)
    metadata_store.upsert_file(
        _record(local_path=str(pdf_path), content_hash=real_hash, file_size=10, modified_time=1_000, status="indexed")
    )
    monkeypatch.setattr(ingest_service, "walk_local_folder", lambda root, config: iter([_discovered(pdf_path)]))
    extract_calls: list[bytes] = []
    monkeypatch.setattr(ingest_service, "extract_pages", lambda data: extract_calls.append(data) or [object()])

    summary = ingest_service.run_ingest(tmp_path, metadata_store, app_config, force_rehash=True)

    assert extract_calls == [pdf_bytes]  # re-read and re-extracted despite mtime/size matching
    assert summary.unchanged == 1  # content did turn out to be identical, just not fast-pathed


def test_unchanged_fast_path_applies_to_a_discovered_but_not_yet_indexed_file(
    monkeypatch, metadata_store, app_config, tmp_path
):
    pdf_path = tmp_path / "worksheet.pdf"
    pdf_path.write_bytes(b"stub")
    metadata_store.upsert_file(
        _record(
            local_path=str(pdf_path), content_hash="hash-a", file_size=10, modified_time=1_000, status="discovered"
        )
    )
    monkeypatch.setattr(ingest_service, "walk_local_folder", lambda root, config: iter([_discovered(pdf_path)]))
    monkeypatch.setattr(ingest_service, "extract_pages", _fail)
    monkeypatch.setattr(Path, "read_bytes", _fail)

    summary = ingest_service.run_ingest(tmp_path, metadata_store, app_config)

    assert summary.unchanged == 1


def test_retries_extraction_failed_file_even_when_mtime_and_size_unchanged(
    monkeypatch, metadata_store, app_config, tmp_path
):
    # A previously-failed file must always be retried, never fast-pathed as "unchanged"
    pdf_path = tmp_path / "corrupt.pdf"
    pdf_path.write_bytes(b"stub-bytes")
    metadata_store.upsert_file(
        _record(
            local_path=str(pdf_path),
            content_hash=None,
            file_size=10,
            modified_time=1_000,
            status="extraction_failed",
            page_count=None,
        )
    )
    monkeypatch.setattr(ingest_service, "walk_local_folder", lambda root, config: iter([_discovered(pdf_path)]))
    monkeypatch.setattr(ingest_service, "extract_pages", lambda data: [object()])  # succeeds this time

    summary = ingest_service.run_ingest(tmp_path, metadata_store, app_config)

    assert summary.unchanged == 0
    assert metadata_store.get_by_path(str(pdf_path)).status == "discovered"


def test_preserves_indexed_status_when_mtime_changes_but_content_is_identical(
    monkeypatch, metadata_store, app_config, tmp_path
):
    # e.g. `touch` or a sync client rewriting identical bytes — must not force a needless re-embed
    pdf_path = tmp_path / "worksheet.pdf"
    pdf_bytes = b"same-content-every-time"
    pdf_path.write_bytes(pdf_bytes)
    real_hash = compute_content_hash(pdf_bytes)
    metadata_store.upsert_file(
        _record(local_path=str(pdf_path), content_hash=real_hash, file_size=10, modified_time=1_000, status="indexed")
    )
    monkeypatch.setattr(
        ingest_service, "walk_local_folder", lambda root, config: iter([_discovered(pdf_path, mtime=2_000)])
    )
    monkeypatch.setattr(ingest_service, "extract_pages", lambda data: [object(), object()])

    summary = ingest_service.run_ingest(tmp_path, metadata_store, app_config)

    assert summary.unchanged == 1
    record = metadata_store.get_by_path(str(pdf_path))
    assert record.status == "indexed"
    assert record.modified_time == 2_000  # stat refreshed even though status was preserved


def test_marks_discovered_when_content_actually_changes(monkeypatch, metadata_store, app_config, tmp_path):
    pdf_path = tmp_path / "worksheet.pdf"
    pdf_path.write_bytes(b"new content entirely")
    metadata_store.upsert_file(
        _record(
            local_path=str(pdf_path), content_hash="stale-hash", file_size=10, modified_time=1_000, status="indexed"
        )
    )
    monkeypatch.setattr(
        ingest_service, "walk_local_folder", lambda root, config: iter([_discovered(pdf_path, mtime=2_000)])
    )
    monkeypatch.setattr(ingest_service, "extract_pages", lambda data: [object()])

    summary = ingest_service.run_ingest(tmp_path, metadata_store, app_config)

    assert summary.updated == 1
    record = metadata_store.get_by_path(str(pdf_path))
    assert record.status == "discovered"
    assert record.content_hash != "stale-hash"
