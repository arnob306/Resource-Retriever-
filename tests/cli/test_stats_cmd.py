"""CLI-level checks for `find-resource stats`."""

from typer.testing import CliRunner

from resource_retriever.cli.app import app

runner = CliRunner()


def test_stats_on_empty_data_dir_reports_zero(tmp_path):
    result = runner.invoke(app, ["stats"], env={"RESOURCE_RETRIEVER_DATA_DIR": str(tmp_path)})

    assert result.exit_code == 0
    assert "Total tracked files: 0" in result.output
    assert "Searches logged: 0" in result.output


def test_stats_reports_counts_after_ingest(tmp_path, sample_pdfs_dir):
    env = {"RESOURCE_RETRIEVER_DATA_DIR": str(tmp_path)}
    ingest_result = runner.invoke(app, ["ingest", str(sample_pdfs_dir)], env=env)
    assert ingest_result.exit_code == 0, ingest_result.stdout

    result = runner.invoke(app, ["stats"], env=env)

    assert result.exit_code == 0
    expected_count = len(list(sample_pdfs_dir.glob("*.pdf")))
    assert f"Total tracked files: {expected_count}" in result.output
    assert "local/discovered" in result.output
