"""Privacy denylist: keeps files that plausibly contain student data out of the index."""

from dataclasses import dataclass, field
from pathlib import Path

from resource_retriever.config import AppConfig


@dataclass(frozen=True)
class ExclusionConfig:
    folder_names: tuple[str, ...] = field(default_factory=tuple)
    path_substrings: tuple[str, ...] = field(default_factory=tuple)
    excluded_files: frozenset[str] = field(default_factory=frozenset)


def _normalize_for_exact_match(path_str: str) -> str:
    """Resolve `path_str` to a canonical absolute form before comparing.

    `excluded_files.txt` is hand-edited, so an entry may use forward slashes, a relative path,
    or `..` segments that would never string-equal the canonical resolved path `local_walker`
    always passes in — without resolving both sides first, such an entry silently fails to
    match and the file it was meant to exclude gets indexed instead. `resolve(strict=False)`
    is used so an entry pointing at a currently-missing path doesn't raise.
    """
    return str(Path(path_str).resolve(strict=False)).lower()


def is_excluded(path: str, config: ExclusionConfig) -> bool:
    """True if `path` matches the denylist by exact match, folder name, or substring."""
    normalized_path = path.lower()
    if _normalize_for_exact_match(path) in {_normalize_for_exact_match(f) for f in config.excluded_files}:
        return True

    path_parts = [part.lower() for part in Path(path).parts]
    denylisted_folders = {name.lower() for name in config.folder_names}
    if any(part in denylisted_folders for part in path_parts):
        return True

    return any(substring.lower() in normalized_path for substring in config.path_substrings)


def load_excluded_files(data_dir: Path) -> frozenset[str]:
    """Read <data_dir>/excluded_files.txt — one path per line, '#' comments allowed."""
    excluded_files_path = data_dir / "excluded_files.txt"
    if not excluded_files_path.exists():
        return frozenset()

    lines = excluded_files_path.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip() for line in lines if line.strip() and not line.strip().startswith("#"))


def load_exclusion_config(app_config: AppConfig) -> ExclusionConfig:
    return ExclusionConfig(
        folder_names=app_config.exclude_folder_names,
        path_substrings=app_config.exclude_path_substrings,
        excluded_files=load_excluded_files(app_config.data_dir),
    )
