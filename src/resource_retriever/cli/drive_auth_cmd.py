"""`find-resource drive-login` — one-time interactive OAuth consent for read-only Drive access."""

from pathlib import Path
from typing import Optional

import typer

from resource_retriever.config import load_app_config
from resource_retriever.ingestion.drive_auth import DriveAuthError, login, token_path


def drive_login(
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="Override the local data directory."),
) -> None:
    """Open a browser for one-time Google Drive OAuth consent and cache the resulting token."""
    app_config = load_app_config(data_dir)
    try:
        login(app_config)
    except DriveAuthError as exc:
        typer.echo(f"Drive login failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Drive credentials saved to {token_path(app_config)}")
