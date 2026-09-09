"""Discovery of PDF files in Google Drive via the Drive v3 API, read-only.

Mirrors local_walker.py's contract: excluded files are still yielded (flagged), never skipped
silently, so the caller can record them in SQLite as status='excluded' rather than losing them.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

from googleapiclient.discovery import Resource

from resource_retriever.ingestion.exclusion import ExclusionConfig, is_excluded

logger = logging.getLogger(__name__)

_PDF_QUERY = "mimeType='application/pdf' and trashed=false"
_FIELDS = "nextPageToken, files(id,name,modifiedTime,md5Checksum,size)"
_PAGE_SIZE = 100


@dataclass(frozen=True)
class DiscoveredDriveFile:
    drive_id: str
    display_name: str
    modified_time: int  # epoch milliseconds UTC, converted from Drive's RFC-3339 modifiedTime
    file_size: int
    md5_checksum: str
    is_excluded: bool


def _rfc3339_to_epoch_millis(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def list_drive_pdfs(service: Resource, exclusion_config: ExclusionConfig) -> Iterator[DiscoveredDriveFile]:
    """Yield every PDF visible to the authenticated account, including Shared Drives.

    `fields=` is explicit and required — without it Drive's API returns only id/name, silently
    dropping modifiedTime/md5Checksum and degrading every re-index pre-check to "assume changed."
    `supportsAllDrives`/`includeItemsFromAllDrives` are required too — Drive API v3 otherwise
    scopes `corpora` to the user's own My Drive and silently omits Shared Drive content.
    Drive-side exclusion checks are applied to `display_name` only (Drive has no OS-style path to
    resolve folder names/substrings against without extra per-file API calls to walk parents).
    """
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=_PDF_QUERY,
                fields=_FIELDS,
                pageSize=_PAGE_SIZE,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        for entry in response.get("files", []):
            md5_checksum = entry.get("md5Checksum")
            if md5_checksum is None:
                # Drive hasn't finished processing this file's content yet (rare, transient) —
                # skip it this run rather than let a missing field abort the whole listing.
                logger.warning("Skipping Drive file %s (%s): no md5Checksum yet", entry["name"], entry["id"])
                continue
            display_name = entry["name"]
            yield DiscoveredDriveFile(
                drive_id=entry["id"],
                display_name=display_name,
                modified_time=_rfc3339_to_epoch_millis(entry["modifiedTime"]),
                file_size=int(entry.get("size", 0)),
                md5_checksum=md5_checksum,
                is_excluded=is_excluded(display_name, exclusion_config),
            )
        page_token = response.get("nextPageToken")
        if not page_token:
            break
