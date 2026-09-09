"""`find-resource index` / `reindex` — embed tracked local files into the vector store."""

from pathlib import Path
from typing import Optional

import typer

from resource_retriever.config import load_app_config
from resource_retriever.embedding.embedder import Embedder
from resource_retriever.indexing.index_service import run_index
from resource_retriever.storage.chroma_vector_store import ChromaVectorStore
from resource_retriever.storage.sqlite_metadata_store import SqliteMetadataStore


def index(
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="Override the local data directory."),
    force_rehash: bool = typer.Option(False, "--force-rehash", help="Skip the mtime/size pre-check and rehash every tracked file."),
) -> None:
    """Extract, chunk, and embed tracked files that are new, changed, or not yet indexed."""
    app_config = load_app_config(data_dir)
    store = SqliteMetadataStore(app_config.metadata_db_path)
    try:
        vector_store = ChromaVectorStore(app_config.chroma_dir)
        embedder = Embedder(app_config)
        summary = run_index(store, vector_store, embedder, app_config, force_rehash=force_rehash)
    finally:
        store.close()

    typer.echo(
        f"Indexed: {summary.new} new, {summary.reprocessed} updated, "
        f"{summary.skipped + summary.touched} skipped (unchanged), {summary.deleted} removed (deleted), "
        f"{summary.failed} failed. Discovered: {summary.discovered}."
    )
