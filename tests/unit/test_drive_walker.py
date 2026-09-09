"""Unit tests for drive_walker.py. The Drive `service` object is faked — no real network calls."""

from datetime import datetime, timezone

from resource_retriever.ingestion.drive_walker import list_drive_pdfs
from resource_retriever.ingestion.exclusion import ExclusionConfig


class FakeDriveService:
    """Mimics service.files().list(...).execute(), paging through `pages` by index."""

    def __init__(self, pages: list[dict]):
        self._pages = pages
        self.list_calls: list[dict] = []

    def files(self):
        return self

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        page_token = kwargs.get("pageToken")
        index = 0 if page_token is None else int(page_token)
        return _FakeRequest(self._pages[index])


class _FakeRequest:
    def __init__(self, response: dict):
        self._response = response

    def execute(self):
        return self._response


def _entry(**overrides):
    base = dict(
        id="drive-1", name="worksheet.pdf", modifiedTime="2024-01-01T12:00:00.000Z", md5Checksum="abc123", size="2048"
    )
    base.update(overrides)
    return base


def test_lists_all_pdfs_across_pages():
    pages = [
        {"files": [_entry(id="a"), _entry(id="b")], "nextPageToken": "1"},
        {"files": [_entry(id="c")]},
    ]
    service = FakeDriveService(pages)

    results = list(list_drive_pdfs(service, ExclusionConfig()))

    assert [r.drive_id for r in results] == ["a", "b", "c"]


def test_converts_modified_time_size_and_hash():
    service = FakeDriveService([{"files": [_entry()]}])

    [result] = list(list_drive_pdfs(service, ExclusionConfig()))

    expected_ms = int(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    assert result.display_name == "worksheet.pdf"
    assert result.md5_checksum == "abc123"
    assert result.file_size == 2048
    assert result.modified_time == expected_ms


def test_flags_excluded_file_by_display_name_but_still_yields_it():
    service = FakeDriveService([{"files": [_entry(name="IEP notes.pdf")]}])
    config = ExclusionConfig(path_substrings=("IEP",))

    [result] = list(list_drive_pdfs(service, config))

    assert result.is_excluded is True


def test_non_excluded_file_is_flagged_false():
    service = FakeDriveService([{"files": [_entry()]}])

    [result] = list(list_drive_pdfs(service, ExclusionConfig()))

    assert result.is_excluded is False


def test_requests_shared_drive_items_not_just_my_drive():
    service = FakeDriveService([{"files": [_entry()]}])

    list(list_drive_pdfs(service, ExclusionConfig()))

    assert service.list_calls[0]["supportsAllDrives"] is True
    assert service.list_calls[0]["includeItemsFromAllDrives"] is True


def test_file_missing_md5_checksum_is_skipped_not_crashed():
    # Arrange — Drive hasn't finished processing this file's content yet (no md5Checksum field)
    pending = _entry(id="pending")
    del pending["md5Checksum"]
    service = FakeDriveService([{"files": [pending, _entry(id="ready")]}])

    # Act — must not raise KeyError
    results = list(list_drive_pdfs(service, ExclusionConfig()))

    # Assert — the pending file is skipped, the ready one still comes through
    assert [r.drive_id for r in results] == ["ready"]
