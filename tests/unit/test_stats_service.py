from resource_retriever.indexing.stats_service import compute_stats
from resource_retriever.models.file_record import FileRecord


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


def test_computes_total_and_breakdown_by_source_and_status(metadata_store):
    metadata_store.upsert_file(_record(id="a", status="indexed"))
    metadata_store.upsert_file(_record(id="b", local_path="/docs/b.pdf", status="indexed"))
    metadata_store.upsert_file(_record(id="c", local_path="/docs/c.pdf", status="excluded"))
    metadata_store.upsert_file(_record(id="d", source_type="drive", local_path=None, drive_id="d1", status="indexed"))

    summary = compute_stats(metadata_store)

    assert summary.total_files == 4
    assert summary.by_source_and_status[("local", "indexed")] == 2
    assert summary.by_source_and_status[("local", "excluded")] == 1
    assert summary.by_source_and_status[("drive", "indexed")] == 1


def test_reports_zero_searches_when_none_logged(metadata_store):
    summary = compute_stats(metadata_store)

    assert summary.total_searches == 0
    assert summary.average_search_latency_ms is None


def test_reports_average_search_latency(metadata_store):
    metadata_store.record_search(query="a", latency_ms=100, result_count=1)
    metadata_store.record_search(query="b", latency_ms=200, result_count=2)

    summary = compute_stats(metadata_store)

    assert summary.total_searches == 2
    assert summary.average_search_latency_ms == 150.0
