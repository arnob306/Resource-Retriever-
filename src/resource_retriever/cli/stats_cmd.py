"""`find-resource stats` — total tracked files by source/status, and search-log performance."""

from pathlib import Path
from typing import Optional

import typer

from resource_retriever.config import load_app_config
from resource_retriever.indexing.stats_service import compute_stats
from resource_retriever.storage.sqlite_metadata_store import SqliteMetadataStore


def stats(
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="Override the local data directory."),
) -> None:
    """Print total files tracked (by source/status) and average search latency."""
    app_config = load_app_config(data_dir)
    store = SqliteMetadataStore(app_config.metadata_db_path)
    try:
        summary = compute_stats(store)
    finally:
        store.close()

    typer.echo(f"Total tracked files: {summary.total_files}")
    for (source, status), count in sorted(summary.by_source_and_status.items()):
        typer.echo(f"  {source}/{status}: {count}")

    average = summary.average_search_latency_ms
    if summary.total_searches == 0 or average is None:
        typer.echo("Searches logged: 0")
    else:
        typer.echo(f"Searches logged: {summary.total_searches}, average latency: {average:.1f}ms")
