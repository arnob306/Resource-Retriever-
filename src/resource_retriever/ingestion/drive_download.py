"""In-memory download of a single Drive file's bytes — never written to disk."""

import io

from googleapiclient.discovery import Resource
from googleapiclient.http import MediaIoBaseDownload


def stream_drive_file_bytes(service: Resource, drive_id: str) -> bytes:
    """Download `drive_id`'s full content into memory and return it as bytes."""
    request = service.files().get_media(fileId=drive_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    return buffer.getvalue()
