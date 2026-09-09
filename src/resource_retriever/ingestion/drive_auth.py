"""Google Drive OAuth: installed-app consent flow, token cache load/refresh/save.

Read-only `drive.readonly` scope only — this tool never writes to Drive. Client secrets and the
refreshed token both live under the local data dir (never committed; see paths.py/.gitignore).
"""

import logging
import os
import stat
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from resource_retriever.config import AppConfig

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
CLIENT_SECRETS_ENV_VAR = "RESOURCE_RETRIEVER_GOOGLE_CLIENT_SECRETS"


class DriveAuthError(Exception):
    """Raised when Drive credentials cannot be obtained, loaded, or refreshed."""


def token_path(app_config: AppConfig) -> Path:
    """Path to the cached OAuth token, under the local data dir."""
    return app_config.data_dir / "drive_token.json"


def client_secrets_path(app_config: AppConfig) -> Path:
    """Path to the OAuth client secrets file (env var override, else under the local data dir)."""
    env_value = os.environ.get(CLIENT_SECRETS_ENV_VAR)
    if env_value:
        return Path(env_value)
    return app_config.data_dir / "google_client_secrets.json"


def login(app_config: AppConfig) -> Credentials:
    """Run the one-time interactive OAuth consent flow and cache the resulting token."""
    secrets_path = client_secrets_path(app_config)
    if not secrets_path.exists():
        raise DriveAuthError(
            f"Google client secrets not found at {secrets_path}. Create an OAuth client "
            "(Desktop app type) in Google Cloud Console, download it, and save it there — or "
            f"point {CLIENT_SECRETS_ENV_VAR} at wherever you saved it."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
    credentials = flow.run_local_server(port=0)
    _save_token(app_config, credentials)
    return credentials


def load_credentials(app_config: AppConfig) -> Credentials:
    """Load the cached token, refreshing it if expired.

    Raises DriveAuthError if there's no cached token or the refresh token has been rejected
    (e.g. Google's 7-day refresh-token expiry while the OAuth consent screen is in Testing
    status — expected, not a bug). Callers must catch this and tell the user to run
    `find-resource drive-login` again rather than let it crash a whole ingest/index run.
    """
    path = token_path(app_config)
    if not path.exists():
        raise DriveAuthError("No cached Drive credentials found. Run `find-resource drive-login` first.")

    try:
        credentials = Credentials.from_authorized_user_file(str(path), SCOPES)
    except (ValueError, OSError) as exc:
        raise DriveAuthError(
            "Cached Drive credentials file is unreadable or corrupted. Run `find-resource drive-login` again."
        ) from exc

    if credentials.valid:
        return credentials
    if not (credentials.expired and credentials.refresh_token):
        raise DriveAuthError("Cached Drive credentials are invalid. Run `find-resource drive-login` again.")

    try:
        credentials.refresh(Request())
    except RefreshError as exc:
        path.unlink(missing_ok=True)
        raise DriveAuthError(
            "Drive refresh token was rejected (commonly the 7-day expiry while the OAuth "
            "consent screen is in Testing status) — run `find-resource drive-login` again."
        ) from exc
    except Exception as exc:
        # A transient network/transport failure — unlike RefreshError, the cached token itself
        # is still presumably valid, so it's kept rather than deleted; just surface a clear error.
        raise DriveAuthError(f"Could not refresh Drive credentials (check your network connection): {exc}") from exc

    _save_token(app_config, credentials)
    return credentials


def _save_token(app_config: AppConfig, credentials: Credentials) -> None:
    """Write the token cache restricted to owner-only access — it carries a live refresh token
    with drive.readonly access to the whole account, so a shared machine's default umask must
    never leave it group/world-readable. chmod is a POSIX-only defense (a no-op on Windows,
    which relies on NTFS user-profile ACLs instead).
    """
    path = token_path(app_config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(credentials.to_json(), encoding="utf-8")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        logger.warning("Could not restrict permissions on %s", path)
