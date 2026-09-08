"""The FileRecord model: one row of tracked-file metadata, source-agnostic."""

from dataclasses import dataclass
from typing import Literal, Optional

SourceType = Literal["local", "drive"]
FileStatus = Literal["discovered", "indexed", "extraction_failed", "excluded"]


@dataclass(frozen=True)
class FileRecord:
    id: str  # synthetic uuid4 — stable identity independent of path or content hash
    source_type: SourceType
    local_path: Optional[str]
    drive_id: Optional[str]
    display_name: str
    content_hash: Optional[str]
    file_size: Optional[int]
    modified_time: int  # epoch milliseconds UTC
    page_count: Optional[int]
    status: FileStatus
    indexed_at: Optional[str]
    created_at: str
