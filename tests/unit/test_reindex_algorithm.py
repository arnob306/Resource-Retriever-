from resource_retriever.indexing.reindex_algorithm import Action, DiscoveredState, decide_action
from resource_retriever.models.file_record import FileRecord


def _record(**overrides) -> FileRecord:
    defaults = dict(
        id="file-1",
        source_type="local",
        local_path="/tmp/a.pdf",
        drive_id=None,
        display_name="a.pdf",
        content_hash="hash-a",
        file_size=100,
        modified_time=1000,
        page_count=1,
        status="indexed",
        indexed_at="2026-01-01T00:00:00+00:00",
        created_at="2026-01-01T00:00:00+00:00",
    )
    defaults.update(overrides)
    return FileRecord(**defaults)


def test_returns_delete_stale_when_file_no_longer_discovered():
    # Arrange
    existing = _record()

    # Act
    action = decide_action(None, existing)

    # Assert
    assert action == Action.DELETE_STALE


def test_returns_new_when_file_has_no_existing_record():
    # Arrange
    discovered = DiscoveredState(content_hash="hash-a", modified_time=1000, file_size=100)

    # Act
    action = decide_action(discovered, None)

    # Assert
    assert action == Action.NEW


def test_returns_skip_when_cheap_precheck_found_no_change():
    # Arrange — content_hash=None means the pre-check decided not to rehash
    discovered = DiscoveredState(content_hash=None, modified_time=1000, file_size=100)
    existing = _record(content_hash="hash-a", modified_time=1000)

    # Act
    action = decide_action(discovered, existing)

    # Assert
    assert action == Action.SKIP


def test_returns_reprocess_when_hash_changed():
    # Arrange
    discovered = DiscoveredState(content_hash="hash-b", modified_time=2000, file_size=200)
    existing = _record(content_hash="hash-a", modified_time=1000)

    # Act
    action = decide_action(discovered, existing)

    # Assert
    assert action == Action.REPROCESS


def test_returns_skip_but_touch_when_hash_unchanged_but_mtime_advanced():
    # Arrange — hash was recomputed (non-None) but matches; mtime advanced anyway
    discovered = DiscoveredState(content_hash="hash-a", modified_time=2000, file_size=100)
    existing = _record(content_hash="hash-a", modified_time=1000)

    # Act
    action = decide_action(discovered, existing)

    # Assert
    assert action == Action.SKIP_BUT_TOUCH


def test_returns_skip_when_hash_unchanged_and_mtime_not_advanced():
    # Arrange
    discovered = DiscoveredState(content_hash="hash-a", modified_time=1000, file_size=100)
    existing = _record(content_hash="hash-a", modified_time=1000)

    # Act
    action = decide_action(discovered, existing)

    # Assert
    assert action == Action.SKIP
