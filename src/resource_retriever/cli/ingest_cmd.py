"""`find-resource ingest` — discover local PDFs, hash + record metadata, no embedding."""

from pathlib import Path
from typing import Optional

import typer

from resource_retriever.config import load_app_config
from resource_retriever.indexing.ingest_service import run_ingest
from resource_retriever.storage.sqlite_metadata_store import SqliteMetadataStore


def ingest(
    local_root: Path = typer.Argument(..., help="Local folder to walk for PDFs."),
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="Override the local data directory."),
) -> None:
    """Discover local PDFs, hash them, and record metadata (no embedding yet)."""
    app_config = load_app_config(data_dir)
    store = SqliteMetadataStore(app_config.metadata_db_path)
    try:
        summary = run_ingest(local_root, store, app_config)
    finally:
        store.close()

    typer.echo(
        f"Discovered {summary.discovered} files "
        f"({summary.new} new, {summary.unchanged} unchanged, {summary.updated} updated, "
        f"{summary.excluded} excluded, {summary.failed} failed) in {local_root}"
    )
