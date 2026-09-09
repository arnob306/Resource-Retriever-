from resource_retriever.config import load_app_config


def test_load_app_config_with_no_config_toml_has_empty_denylists(tmp_path):
    config = load_app_config(data_dir_override=tmp_path)

    assert config.exclude_folder_names == ()
    assert config.exclude_path_substrings == ()


def test_load_app_config_reads_exclude_denylist_from_config_toml(tmp_path):
    (tmp_path / "config.toml").write_text(
        '[exclude]\n'
        'folder_names = ["student work", "gradebook"]\n'
        'path_substrings = ["IEP", "marked"]\n',
        encoding="utf-8",
    )

    config = load_app_config(data_dir_override=tmp_path)

    assert config.exclude_folder_names == ("student work", "gradebook")
    assert config.exclude_path_substrings == ("IEP", "marked")


def test_load_app_config_creates_the_data_dir_if_missing(tmp_path):
    data_dir = tmp_path / "does-not-exist-yet"

    config = load_app_config(data_dir_override=data_dir)

    assert config.data_dir.exists()
