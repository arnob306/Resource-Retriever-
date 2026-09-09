"""Recursive discovery of PDF files under a local folder."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from resource_retriever.ingestion.exclusion import ExclusionConfig, is_excluded

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscoveredFile:
    local_path: str
    display_name: str
    modified_time: int  # epoch milliseconds UTC
    file_size: int
    is_excluded: bool


def _is_contained(resolved_path: Path, resolved_root: Path) -> bool:
    """True if `resolved_path` is `resolved_root` or lives underneath it.

    Both paths must already be fully resolved (symlinks/junctions followed). This is what
    catches a symlinked or junctioned directory *inside* the scanned root whose real target
    lives elsewhere on disk — `Path.rglob` follows such links on Python < 3.13 with no opt-out,
    so without this check a file reachable only through such a link could be silently ingested
    even though its real location doesn't match the privacy exclusion denylist.
    """
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def walk_local_folder(root: Path, exclusion_config: ExclusionConfig) -> Iterator[DiscoveredFile]:
    """Yield every *.pdf under `root`. Excluded files are still yielded (flagged), never skipped
    silently, so the caller can record them in SQLite as status='excluded' rather than losing them.

    A file reached only via a symlink/junction that points outside `root` is skipped entirely
    (not yielded) rather than flagged excluded, since it never belonged to the scanned tree in
    the first place — but it's logged, never dropped without a trace.
    """
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"Local root does not exist: {root}")
    resolved_root = root.resolve()

    for path in sorted(root.rglob("*.pdf")):
        if not path.is_file():
            continue
        resolved_path = path.resolve()
        if not _is_contained(resolved_path, resolved_root):
            logger.warning(
                "Skipping %s: resolves to %s, outside the scanned root %s "
                "(likely a symlink or junction) — excluded from indexing for safety",
                path,
                resolved_path,
                resolved_root,
            )
            continue
        absolute_path = str(resolved_path)
        stat = path.stat()
        yield DiscoveredFile(
            local_path=absolute_path,
            display_name=path.name,
            modified_time=int(stat.st_mtime * 1000),
            file_size=stat.st_size,
            is_excluded=is_excluded(absolute_path, exclusion_config),
        )
