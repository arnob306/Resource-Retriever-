"""CLI-level check for `find-resource drive-login` error handling.

The success path (real OAuth browser consent) can't be exercised in CI/tests — see
tests/unit/test_drive_auth.py for the mocked-consent-flow coverage of drive_auth.login() itself.
"""

from typer.testing import CliRunner

from resource_retriever.cli.app import app

runner = CliRunner()


def test_drive_login_without_client_secrets_fails_cleanly(tmp_path):
    result = runner.invoke(app, ["drive-login"], env={"RESOURCE_RETRIEVER_DATA_DIR": str(tmp_path)})

    assert result.exit_code == 1
    assert "client secrets not found" in result.output
