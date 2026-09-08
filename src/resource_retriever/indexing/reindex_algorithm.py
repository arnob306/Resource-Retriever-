"""Pure decision logic for incremental re-indexing. No I/O — trivially unit-testable.

`discovered.content_hash` is Optional[str]: None means the caller's cheap mtime/size pre-check
decided the file is unchanged and deliberately did not (re)hash it; a non-None value means the
file was actually hashed this run. This distinction is what keeps the pre-check and this function
in agreement — comparing hashes unconditionally would misread every unchanged file (which never
gets rehashed) as REPROCESS.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from resource_retriever.models.file_record import FileRecord


class Action(Enum):
    NEW = auto()
    REPROCESS = auto()
    SKIP_BUT_TOUCH = auto()
    SKIP = auto()
    DELETE_STALE = auto()


@dataclass(frozen=True)
class DiscoveredState:
    content_hash: Optional[str]  # None == cheap pre-check said unchanged, not rehashed
    modified_time: int  # epoch milliseconds UTC
    file_size: int


def decide_action(discovered: Optional[DiscoveredState], existing: Optional[FileRecord]) -> Action:
    if discovered is None:
        return Action.DELETE_STALE
    if existing is None:
        return Action.NEW
    if discovered.content_hash is None:
        return Action.SKIP
    if discovered.content_hash != existing.content_hash:
        return Action.REPROCESS
    return Action.SKIP_BUT_TOUCH if discovered.modified_time > existing.modified_time else Action.SKIP
