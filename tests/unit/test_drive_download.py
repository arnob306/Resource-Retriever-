"""Unit tests for drive_download.py. MediaIoBaseDownload is faked — no real network calls."""

from unittest.mock import MagicMock

from resource_retriever.ingestion import drive_download


class FakeDownloader:
    """Mimics MediaIoBaseDownload: writes fake chunks into the buffer across next_chunk() calls."""

    def __init__(self, buffer, _request, chunks: list[bytes]):
        self._buffer = buffer
        self._chunks = list(chunks)

    def next_chunk(self):
        chunk = self._chunks.pop(0)
        self._buffer.write(chunk)
        return None, len(self._chunks) == 0


def test_stream_drive_file_bytes_assembles_full_content_across_chunks(monkeypatch):
    fake_service = MagicMock()
    fake_request = MagicMock()
    fake_service.files.return_value.get_media.return_value = fake_request
    chunks = [b"PDF-part-1-", b"PDF-part-2"]
    monkeypatch.setattr(
        drive_download, "MediaIoBaseDownload", lambda buffer, request: FakeDownloader(buffer, request, chunks)
    )

    result = drive_download.stream_drive_file_bytes(fake_service, "drive-id-123")

    assert result == b"PDF-part-1-PDF-part-2"
    fake_service.files.return_value.get_media.assert_called_once_with(fileId="drive-id-123")


def test_stream_drive_file_bytes_handles_a_single_chunk(monkeypatch):
    fake_service = MagicMock()
    monkeypatch.setattr(
        drive_download, "MediaIoBaseDownload", lambda buffer, request: FakeDownloader(buffer, request, [b"whole-file"])
    )

    result = drive_download.stream_drive_file_bytes(fake_service, "drive-id-456")

    assert result == b"whole-file"
