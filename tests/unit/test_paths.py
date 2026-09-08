from pathlib import Path

from resource_retriever.paths import DATA_DIR_ENV_VAR, resolve_data_dir

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_default_data_dir_resolves_outside_the_repo_when_unset(monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)

    data_dir = resolve_data_dir()

    assert data_dir == Path.home() / ".resource_retriever"
    assert REPO_ROOT not in data_dir.parents and data_dir != REPO_ROOT


def test_env_var_override_takes_effect_when_no_explicit_override_given(monkeypatch, tmp_path):
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(tmp_path))

    assert resolve_data_dir() == tmp_path


def test_explicit_override_wins_over_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(tmp_path / "from-env"))
    explicit = tmp_path / "from-override"

    assert resolve_data_dir(explicit) == explicit
