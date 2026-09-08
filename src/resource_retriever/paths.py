"""Resolution of the local data directory used for all persisted state."""

import os
from pathlib import Path

DATA_DIR_ENV_VAR = "RESOURCE_RETRIEVER_DATA_DIR"
_DEFAULT_DATA_DIR = Path.home() / ".resource_retriever"


def resolve_data_dir(override: Path | None = None) -> Path:
    """Return the directory all local state (SQLite DB, vectors, credentials) lives in.

    Defaults outside the repo so nothing here is ever accidentally git-tracked,
    even if a caller forgets the .gitignore layer.
    """
    if override is not None:
        return Path(override)
    env_value = os.environ.get(DATA_DIR_ENV_VAR)
    if env_value:
        return Path(env_value)
    return _DEFAULT_DATA_DIR


def ensure_data_dir_exists(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
