from typer.testing import CliRunner

from resource_retriever.cli.app import app

runner = CliRunner()


def test_ingest_command_prints_summary_counts(tmp_path, sample_pdfs_dir, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("RESOURCE_RETRIEVER_DATA_DIR", str(data_dir))

    result = runner.invoke(app, ["ingest", str(sample_pdfs_dir)])

    assert result.exit_code == 0
    assert "Discovered" in result.stdout
    assert "new" in result.stdout
    assert "unchanged" in result.stdout


def test_ingest_command_accepts_force_rehash_flag(tmp_path, sample_pdfs_dir, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("RESOURCE_RETRIEVER_DATA_DIR", str(data_dir))
    runner.invoke(app, ["ingest", str(sample_pdfs_dir)])

    result = runner.invoke(app, ["ingest", str(sample_pdfs_dir), "--force-rehash"])

    assert result.exit_code == 0
    assert "Discovered" in result.stdout


def test_ingest_command_fails_clearly_on_missing_root(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("RESOURCE_RETRIEVER_DATA_DIR", str(data_dir))
    missing_root = tmp_path / "does_not_exist"

    result = runner.invoke(app, ["ingest", str(missing_root)])

    assert result.exit_code != 0
