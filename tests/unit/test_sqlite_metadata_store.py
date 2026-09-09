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
        status="discovered",
        indexed_at=None,
        created_at="2024-01-01T00:00:00+00:00",
    )
    base.update(overrides)
    return FileRecord(**base)


def test_upsert_then_get_by_path_returns_record(metadata_store):
    metadata_store.upsert_file(_record())

    result = metadata_store.get_by_path("/docs/worksheet.pdf")

    assert result is not None
    assert result.id == "file-1"
    assert result.content_hash == "hash-a"


def test_upsert_with_same_id_updates_existing_row(metadata_store):
    metadata_store.upsert_file(_record())
    metadata_store.upsert_file(_record(content_hash="hash-b", status="indexed"))

    result = metadata_store.get_by_path("/docs/worksheet.pdf")

    assert result.content_hash == "hash-b"
    assert result.status == "indexed"


def test_get_by_hash_returns_matching_record(metadata_store):
    metadata_store.upsert_file(_record())

    result = metadata_store.get_by_hash("hash-a")

    assert result is not None
    assert result.id == "file-1"


def test_get_by_drive_id_returns_matching_record(metadata_store):
    metadata_store.upsert_file(
        _record(id="file-2", local_path=None, drive_id="drive-abc", source_type="drive")
    )

    result = metadata_store.get_by_drive_id("drive-abc")

    assert result is not None
    assert result.id == "file-2"


def test_list_stale_returns_only_records_not_in_discovered_set(metadata_store):
    metadata_store.upsert_file(_record(id="file-1"))
    metadata_store.upsert_file(_record(id="file-2", local_path="/docs/other.pdf"))

    stale = metadata_store.list_stale({"file-1"})

    assert [record.id for record in stale] == ["file-2"]


def test_list_stale_excludes_excluded_status_rows(metadata_store):
    metadata_store.upsert_file(_record(id="file-1", status="excluded"))

    stale = metadata_store.list_stale(set())

    assert stale == []


def test_list_stale_scoped_to_source_type_ignores_other_sources(metadata_store):
    # Arrange — a Drive-sourced record that a local-only run never discovered this run
    metadata_store.upsert_file(_record(id="local-1"))
    metadata_store.upsert_file(
        _record(id="drive-1", source_type="drive", local_path=None, drive_id="drive-abc")
    )

    # Act — a local-only index run scopes list_stale to source_type="local"
    stale = metadata_store.list_stale(set(), source_type="local")

    # Assert — the drive record must never be purged by a run that only walked local files
    assert [record.id for record in stale] == ["local-1"]


def test_delete_file_removes_row(metadata_store):
    metadata_store.upsert_file(_record())

    metadata_store.delete_file("file-1")

    assert metadata_store.get_by_path("/docs/worksheet.pdf") is None


def test_get_by_path_returns_none_when_not_found(metadata_store):
    result = metadata_store.get_by_path("/does/not/exist.pdf")

    assert result is None


def test_search_stats_returns_zero_and_none_when_nothing_logged(metadata_store):
    total, average = metadata_store.search_stats()

    assert total == 0
    assert average is None


def test_search_stats_averages_logged_latencies(metadata_store):
    metadata_store.record_search(query="a", latency_ms=100, result_count=1)
    metadata_store.record_search(query="b", latency_ms=300, result_count=0)

    total, average = metadata_store.search_stats()

    assert total == 2
    assert average == 200.0
