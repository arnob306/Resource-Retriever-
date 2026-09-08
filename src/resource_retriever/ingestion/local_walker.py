"""Recursive discovery of PDF files under a local folder."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from resource_retriever.ingestion.exclusion import ExclusionConfig, is_excluded


@dataclass(frozen=True)
class DiscoveredFile:
    local_path: str
    display_name: str
    modified_time: int  # epoch milliseconds UTC
    file_size: int
    is_excluded: bool


def walk_local_folder(root: Path, exclusion_config: ExclusionConfig) -> Iterator[DiscoveredFile]:
    """Yield every *.pdf under `root`. Excluded files are still yielded (flagged), never skipped
    silently, so the caller can record them in SQLite as status='excluded' rather than losing them.
    """
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"Local root does not exist: {root}")

    for path in sorted(root.rglob("*.pdf")):
        if not path.is_file():
            continue
        absolute_path = str(path.resolve())
        stat = path.stat()
        yield DiscoveredFile(
            local_path=absolute_path,
            display_name=path.name,
            modified_time=int(stat.st_mtime * 1000),
            file_size=stat.st_size,
            is_excluded=is_excluded(absolute_path, exclusion_config),
        )
