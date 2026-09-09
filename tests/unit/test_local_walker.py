import pytest

from resource_retriever.ingestion.exclusion import ExclusionConfig
from resource_retriever.ingestion.local_walker import _is_contained, walk_local_folder


def test_is_contained_true_for_path_under_root(tmp_path):
    root = tmp_path / "root"
    nested = root / "sub" / "file.pdf"

    assert _is_contained(nested, root) is True


def test_is_contained_true_for_root_itself(tmp_path):
    root = tmp_path / "root"

    assert _is_contained(root, root) is True


def test_is_contained_false_for_path_outside_root(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "elsewhere" / "file.pdf"

    assert _is_contained(outside, root) is False


def test_walk_local_folder_skips_file_reached_via_symlink_outside_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.pdf").write_bytes(b"%PDF-1.4 fake")

    link = root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires elevated privileges/Developer Mode on this machine")

    discovered = list(walk_local_folder(root, ExclusionConfig()))

    assert discovered == []


def test_walk_local_folder_still_yields_ordinary_files_under_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "worksheet.pdf").write_bytes(b"%PDF-1.4 fake")

    discovered = list(walk_local_folder(root, ExclusionConfig()))

    assert len(discovered) == 1
    assert discovered[0].display_name == "worksheet.pdf"
