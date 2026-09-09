"""`find-resource find` — semantic search over indexed local files."""

from pathlib import Path
from typing import Optional

import typer

from resource_retriever.config import load_app_config
from resource_retriever.embedding.embedder import Embedder
from resource_retriever.search.search_service import find as run_find
from resource_retriever.storage.chroma_vector_store import ChromaVectorStore
from resource_retriever.storage.sqlite_metadata_store import SqliteMetadataStore


def find(
    query: str = typer.Argument(..., help="Natural-language search query."),
    top_k: int = typer.Option(5, "--top-k", help="Maximum number of results to return."),
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="Override the local data directory."),
) -> None:
    """Search indexed files for QUERY and print ranked results."""
    app_config = load_app_config(data_dir)
    store = SqliteMetadataStore(app_config.metadata_db_path)
    try:
        vector_store = ChromaVectorStore(app_config.chroma_dir)
        embedder = Embedder(app_config)
        outcome = run_find(query, store, vector_store, embedder, top_k=top_k)
    finally:
        store.close()

    if not outcome.results:
        typer.echo("No results found.")
    else:
        for i, result in enumerate(outcome.results, start=1):
            typer.echo(f"{i}. [{result.score:.2f}] {result.file_path} — page {result.page_number}")
            typer.echo(f'   "{result.snippet}"')
            typer.echo(f"   Open: {result.open_command}")
    typer.echo(f"Search latency: {outcome.latency_ms}ms")
