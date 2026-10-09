from pathlib import Path

from honeywagon.files import MAX_FILE_BYTES, load_project


def reasons(root: Path) -> dict[str, str]:
    return {item.what: item.reason for item in load_project(root).not_read}


def test_text_files_are_read_in_a_fixed_order_with_forward_slashes(
    tmp_path: Path,
) -> None:
    (tmp_path / "skills" / "b").mkdir(parents=True)
    (tmp_path / "skills" / "b" / "SKILL.md").write_text("b")
    (tmp_path / "a.json").write_text("{}")

    project = load_project(tmp_path)

    assert [file.path for file in project.files] == ["a.json", "skills/b/SKILL.md"]
    assert project.not_read == ()


def test_other_file_types_are_reported_as_not_read(tmp_path: Path) -> None:
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")
    (tmp_path / "app.js").write_text("console.log(1)")

    assert reasons(tmp_path) == {"app.js": "file_type", "logo.png": "file_type"}


def test_large_and_binary_files_are_reported_as_not_read(tmp_path: Path) -> None:
    (tmp_path / "big.md").write_text("x" * (MAX_FILE_BYTES + 1))
    (tmp_path / "binary.txt").write_bytes(b"\xff\xfe\x00\x01")

    assert reasons(tmp_path) == {"big.md": "too_large", "binary.txt": "not_text"}


def test_dependency_and_cache_folders_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.json").write_text("{}")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.txt").write_text("x")

    project = load_project(tmp_path)

    assert project.files == ()
    assert project.not_read == ()
