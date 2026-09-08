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
