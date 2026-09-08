"""Typer app aggregator — entry point registered in pyproject.toml as find-resource."""

import typer

from resource_retriever.cli.ingest_cmd import ingest

app = typer.Typer(help="Local semantic search over teaching resource PDFs.")


@app.callback()
def _main() -> None:
    """Keep `find-resource <command> ...` subcommand dispatch even while only one command exists.

    Without this callback, Typer collapses a single-command app into a bare top-level command
    (dropping the need for the "ingest" subcommand name) — undesired since later phases add
    `index`/`find`/`drive-login`/`stats` as siblings of `ingest`.
    """


app.command(name="ingest")(ingest)
