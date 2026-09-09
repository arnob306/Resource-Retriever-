from resource_retriever.ingestion.exclusion import ExclusionConfig, is_excluded


def test_path_in_denylisted_folder_is_excluded():
    config = ExclusionConfig(folder_names=("student work",))

    result = is_excluded(r"C:\docs\Student Work\test.pdf", config)

    assert result is True


def test_unrelated_path_is_not_excluded():
    config = ExclusionConfig(folder_names=("student work",))

    result = is_excluded(r"C:\docs\worksheets\quadratics.pdf", config)

    assert result is False


def test_path_substring_match_excludes():
    config = ExclusionConfig(path_substrings=("gradebook",))

    result = is_excluded(r"C:\docs\2024_gradebook_final.pdf", config)

    assert result is True


def test_exact_file_in_excluded_files_list_is_excluded():
    config = ExclusionConfig(excluded_files=frozenset({r"c:\docs\iep_notes.pdf"}))

    result = is_excluded(r"C:\docs\iep_notes.pdf", config)

    assert result is True


def test_empty_config_excludes_nothing():
    config = ExclusionConfig()

    result = is_excluded(r"C:\docs\worksheets\quadratics.pdf", config)

    assert result is False


def test_exact_match_normalizes_forward_slashes_in_denylist_entry(tmp_path):
    target = tmp_path / "iep_notes.pdf"
    target.write_bytes(b"%PDF-1.4 fake")
    forward_slash_entry = str(target).replace("\\", "/")
    config = ExclusionConfig(excluded_files=frozenset({forward_slash_entry}))

    result = is_excluded(str(target), config)

    assert result is True


def test_exact_match_normalizes_relative_denylist_entry(tmp_path, monkeypatch):
    target = tmp_path / "gradebook.pdf"
    target.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.chdir(tmp_path)
    config = ExclusionConfig(excluded_files=frozenset({"gradebook.pdf"}))

    result = is_excluded(str(target.resolve()), config)

    assert result is True
