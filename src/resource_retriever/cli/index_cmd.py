"""`find-resource index` / `reindex` — embed tracked files (local and/or Drive) into the vector store."""

from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from googleapiclient.discovery import build

from resource_retriever.config import load_app_config
from resource_retriever.embedding.embedder import Embedder
from resource_retriever.indexing.drive_index_service import run_drive_index
from resource_retriever.indexing.index_service import IndexSummary, run_index
from resource_retriever.ingestion.drive_auth import DriveAuthError, load_credentials
from resource_retriever.storage.chroma_vector_store import ChromaVectorStore
from resource_retriever.storage.sqlite_metadata_store import SqliteMetadataStore


class Source(str, Enum):
    local = "local"
    drive = "drive"
    all = "all"


def index(
    source: Source = typer.Option(Source.local, "--source", help="Which tracked files to (re)index."),
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="Override the local data directory."),
    force_rehash: bool = typer.Option(
        False, "--force-rehash", help="Local only: skip the mtime/size pre-check and rehash every tracked file."
    ),
) -> None:
    """Extract, chunk, and embed tracked files that are new, changed, or not yet indexed."""
    app_config = load_app_config(data_dir)
    store = SqliteMetadataStore(app_config.metadata_db_path)
    try:
        vector_store = ChromaVectorStore(app_config.chroma_dir)
        embedder = Embedder(app_config)
        summary = IndexSummary(discovered=0, new=0, reprocessed=0, touched=0, skipped=0, deleted=0, failed=0)

        if source in (Source.local, Source.all):
            summary = _add_summaries(summary, run_index(store, vector_store, embedder, app_config, force_rehash=force_rehash))

        if source in (Source.drive, Source.all):
            try:
                credentials = load_credentials(app_config)
                drive_service = build("drive", "v3", credentials=credentials)
            except DriveAuthError as exc:
                typer.echo(f"Drive index skipped: {exc}", err=True)
                if source == Source.drive:
                    raise typer.Exit(code=1) from exc
            except Exception as exc:
                typer.echo(f"Drive index skipped: could not reach Google Drive: {exc}", err=True)
                if source == Source.drive:
                    raise typer.Exit(code=1) from exc
            else:
                summary = _add_summaries(summary, run_drive_index(drive_service, store, vector_store, embedder, app_config))
    finally:
        store.close()

    typer.echo(
        f"Indexed: {summary.new} new, {summary.reprocessed} updated, "
        f"{summary.skipped + summary.touched} skipped (unchanged), {summary.deleted} removed (deleted), "
        f"{summary.failed} failed. Discovered: {summary.discovered}."
    )


def _add_summaries(a: IndexSummary, b: IndexSummary) -> IndexSummary:
    return IndexSummary(
        discovered=a.discovered + b.discovered,
        new=a.new + b.new,
        reprocessed=a.reprocessed + b.reprocessed,
        touched=a.touched + b.touched,
        skipped=a.skipped + b.skipped,
        deleted=a.deleted + b.deleted,
        failed=a.failed + b.failed,
    )
