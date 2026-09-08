"""Application configuration: data directory location plus indexing/embedding tunables."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from resource_retriever.paths import ensure_data_dir_exists, resolve_data_dir


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_window_tokens: int = 220
    chunk_overlap_tokens: int = 40
    query_prefix: str = ""
    document_prefix: str = ""
    normalize_embeddings: bool = True
    exclude_folder_names: tuple[str, ...] = field(default_factory=tuple)
    exclude_path_substrings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def metadata_db_path(self) -> Path:
        return self.data_dir / "metadata.sqlite3"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"


def load_app_config(data_dir_override: Path | None = None) -> AppConfig:
    """Resolve the data dir, ensure it exists, and layer in <data_dir>/config.toml if present."""
    data_dir = ensure_data_dir_exists(resolve_data_dir(data_dir_override))

    folder_names: tuple[str, ...] = ()
    path_substrings: tuple[str, ...] = ()
    config_toml_path = data_dir / "config.toml"
    if config_toml_path.exists():
        raw = tomllib.loads(config_toml_path.read_text(encoding="utf-8"))
        exclude_section = raw.get("exclude", {})
        folder_names = tuple(exclude_section.get("folder_names", []))
        path_substrings = tuple(exclude_section.get("path_substrings", []))

    return AppConfig(
        data_dir=data_dir,
        exclude_folder_names=folder_names,
        exclude_path_substrings=path_substrings,
    )
