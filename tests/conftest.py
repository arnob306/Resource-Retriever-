from pathlib import Path

import pytest

from resource_retriever.config import AppConfig
from resource_retriever.storage.sqlite_metadata_store import SqliteMetadataStore

SAMPLE_PDFS_DIR = Path(__file__).resolve().parent.parent / "sample_pdfs"


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def app_config(tmp_data_dir: Path) -> AppConfig:
    return AppConfig(data_dir=tmp_data_dir)


@pytest.fixture
def metadata_store(tmp_data_dir: Path):
    store = SqliteMetadataStore(tmp_data_dir / "metadata.sqlite3")
    yield store
    store.close()


@pytest.fixture
def sample_pdfs_dir() -> Path:
    return SAMPLE_PDFS_DIR


@pytest.fixture
def sample_pdf_bytes(sample_pdfs_dir: Path) -> bytes:
    pdf_path = next(sample_pdfs_dir.glob("*.pdf"))
    return pdf_path.read_bytes()
