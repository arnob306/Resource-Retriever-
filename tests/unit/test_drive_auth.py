"""Unit tests for drive_auth.py. All Google OAuth calls are mocked — no real network/credentials."""

import json
import stat
import sys
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import RefreshError

from resource_retriever.ingestion import drive_auth
from resource_retriever.ingestion.drive_auth import DriveAuthError


def test_login_raises_clear_error_when_client_secrets_missing(app_config):
    with pytest.raises(DriveAuthError, match="client secrets not found"):
        drive_auth.login(app_config)


def test_login_saves_token_after_successful_consent(monkeypatch, app_config):
    (app_config.data_dir / "google_client_secrets.json").write_text("{}", encoding="utf-8")
    fake_credentials = MagicMock()
    fake_credentials.to_json.return_value = json.dumps({"token": "fake-token"})
    fake_flow = MagicMock()
    fake_flow.run_local_server.return_value = fake_credentials
    monkeypatch.setattr(drive_auth.InstalledAppFlow, "from_client_secrets_file", MagicMock(return_value=fake_flow))

    result = drive_auth.login(app_config)

    assert result is fake_credentials
    saved = drive_auth.token_path(app_config)
    assert json.loads(saved.read_text(encoding="utf-8")) == {"token": "fake-token"}


def test_client_secrets_path_prefers_env_var(monkeypatch, app_config, tmp_path):
    override = tmp_path / "custom_secrets.json"
    monkeypatch.setenv(drive_auth.CLIENT_SECRETS_ENV_VAR, str(override))

    assert drive_auth.client_secrets_path(app_config) == override


def test_load_credentials_raises_when_no_token_cached(app_config):
    with pytest.raises(DriveAuthError, match="No cached Drive credentials"):
        drive_auth.load_credentials(app_config)


def test_load_credentials_returns_valid_cached_token_without_refresh(monkeypatch, app_config):
    drive_auth.token_path(app_config).parent.mkdir(parents=True, exist_ok=True)
    drive_auth.token_path(app_config).write_text("{}", encoding="utf-8")
    fake_credentials = MagicMock(valid=True)
    monkeypatch.setattr(drive_auth.Credentials, "from_authorized_user_file", MagicMock(return_value=fake_credentials))

    result = drive_auth.load_credentials(app_config)

    assert result is fake_credentials
    fake_credentials.refresh.assert_not_called()


def test_load_credentials_refreshes_expired_token_and_resaves(monkeypatch, app_config):
    drive_auth.token_path(app_config).parent.mkdir(parents=True, exist_ok=True)
    drive_auth.token_path(app_config).write_text("{}", encoding="utf-8")
    fake_credentials = MagicMock(valid=False, expired=True, refresh_token="rt")
    fake_credentials.to_json.return_value = json.dumps({"token": "refreshed"})
    monkeypatch.setattr(drive_auth.Credentials, "from_authorized_user_file", MagicMock(return_value=fake_credentials))

    result = drive_auth.load_credentials(app_config)

    assert result is fake_credentials
    fake_credentials.refresh.assert_called_once()
    assert json.loads(drive_auth.token_path(app_config).read_text(encoding="utf-8")) == {"token": "refreshed"}


def test_load_credentials_raises_when_invalid_and_not_refreshable(monkeypatch, app_config):
    drive_auth.token_path(app_config).parent.mkdir(parents=True, exist_ok=True)
    drive_auth.token_path(app_config).write_text("{}", encoding="utf-8")
    fake_credentials = MagicMock(valid=False, expired=False, refresh_token=None)
    monkeypatch.setattr(drive_auth.Credentials, "from_authorized_user_file", MagicMock(return_value=fake_credentials))

    with pytest.raises(DriveAuthError, match="invalid"):
        drive_auth.load_credentials(app_config)


@pytest.mark.skipif(sys.platform == "win32", reason="chmod doesn't enforce POSIX permission bits on Windows")
def test_saved_token_is_restricted_to_owner_only(monkeypatch, app_config):
    (app_config.data_dir / "google_client_secrets.json").write_text("{}", encoding="utf-8")
    fake_credentials = MagicMock()
    fake_credentials.to_json.return_value = json.dumps({"token": "fake-token"})
    fake_flow = MagicMock()
    fake_flow.run_local_server.return_value = fake_credentials
    monkeypatch.setattr(drive_auth.InstalledAppFlow, "from_client_secrets_file", MagicMock(return_value=fake_flow))

    drive_auth.login(app_config)

    mode = stat.S_IMODE(drive_auth.token_path(app_config).stat().st_mode)
    assert mode == stat.S_IRUSR | stat.S_IWUSR


def test_load_credentials_wraps_corrupted_token_file_as_drive_auth_error(monkeypatch, app_config):
    drive_auth.token_path(app_config).parent.mkdir(parents=True, exist_ok=True)
    drive_auth.token_path(app_config).write_text("not valid json", encoding="utf-8")
    monkeypatch.setattr(
        drive_auth.Credentials, "from_authorized_user_file", MagicMock(side_effect=ValueError("bad token file"))
    )

    with pytest.raises(DriveAuthError, match="unreadable or corrupted"):
        drive_auth.load_credentials(app_config)


def test_load_credentials_deletes_token_and_raises_on_refresh_error(monkeypatch, app_config):
    token_file = drive_auth.token_path(app_config)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text("{}", encoding="utf-8")
    fake_credentials = MagicMock(valid=False, expired=True, refresh_token="rt")
    fake_credentials.refresh.side_effect = RefreshError("invalid_grant")
    monkeypatch.setattr(drive_auth.Credentials, "from_authorized_user_file", MagicMock(return_value=fake_credentials))

    with pytest.raises(DriveAuthError, match="rejected"):
        drive_auth.load_credentials(app_config)

    assert not token_file.exists()
