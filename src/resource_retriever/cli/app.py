"""Typer app aggregator — entry point registered in pyproject.toml as find-resource."""

import typer

from resource_retriever.cli.drive_auth_cmd import drive_login
from resource_retriever.cli.find_cmd import find
from resource_retriever.cli.index_cmd import index
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
app.command(name="index")(index)
app.command(name="reindex")(index)
app.command(name="find")(find)
app.command(name="drive-login")(drive_login)
