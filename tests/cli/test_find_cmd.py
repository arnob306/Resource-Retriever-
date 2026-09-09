"""CLI-level check for `find-resource find` against a real ingested + indexed sample corpus.

Uses the real embedder and real Chroma store (same tradeoff as the Phase 2 integration test) —
this is the one place that verifies `ingest` -> `index` -> `find` agree with each other through
the actual Typer command surface, not just the underlying service functions.
"""

import pytest
from typer.testing import CliRunner

from resource_retriever.cli.app import app

pytestmark = pytest.mark.integration

runner = CliRunner()


@pytest.fixture(scope="module")
def indexed_data_dir(tmp_path_factory, sample_pdfs_dir):
    data_dir = tmp_path_factory.mktemp("phase3_cli_data")
    env = {"RESOURCE_RETRIEVER_DATA_DIR": str(data_dir)}

    ingest_result = runner.invoke(app, ["ingest", str(sample_pdfs_dir)], env=env)
    assert ingest_result.exit_code == 0, ingest_result.stdout

    index_result = runner.invoke(app, ["index"], env=env)
    assert index_result.exit_code == 0, index_result.stdout

    return data_dir


def test_find_returns_the_matching_file_page_and_open_command(indexed_data_dir):
    result = runner.invoke(
        app, ["find", "quadratic word problems", "--top-k", "3"], env={"RESOURCE_RETRIEVER_DATA_DIR": str(indexed_data_dir)}
    )

    assert result.exit_code == 0
    assert "year9_quadratics_worksheet.pdf" in result.stdout
    assert "page" in result.stdout
    assert "Open:" in result.stdout
    assert "Search latency:" in result.stdout


def test_find_with_no_matching_data_dir_reports_no_results(tmp_path):
    empty_data_dir = tmp_path / "empty"

    result = runner.invoke(app, ["find", "anything at all"], env={"RESOURCE_RETRIEVER_DATA_DIR": str(empty_data_dir)})

    assert result.exit_code == 0
    assert "No results found." in result.stdout
