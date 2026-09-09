"""CLI-level checks for `find-resource index --source ...` error handling.

Only exercises the "no Drive credentials cached" path here — a full Drive index run needs a real
Drive service, which is covered at the unit level in tests/unit/test_drive_index_service.py. The
local-only path is already covered end-to-end by tests/cli/test_find_cmd.py.
"""

from typer.testing import CliRunner

from resource_retriever.cli.app import app

runner = CliRunner()


def test_index_source_drive_without_credentials_fails_cleanly(tmp_path):
    result = runner.invoke(app, ["index", "--source", "drive"], env={"RESOURCE_RETRIEVER_DATA_DIR": str(tmp_path)})

    assert result.exit_code == 1
    assert "drive-login" in result.output


def test_index_source_all_without_drive_credentials_still_indexes_local(tmp_path):
    result = runner.invoke(app, ["index", "--source", "all"], env={"RESOURCE_RETRIEVER_DATA_DIR": str(tmp_path)})

    assert result.exit_code == 0
    assert "Drive index skipped" in result.output
    assert "Indexed:" in result.output
