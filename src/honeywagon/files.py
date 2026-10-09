"""Read the audited project. Nothing here writes, and nothing outside it is read."""

import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from honeywagon.models import NotChecked

SKIPPED_FOLDERS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "node_modules",
        "venv",
    }
)
TEXT_SUFFIXES = frozenset(
    {
        ".cfg",
        ".env",
        ".ini",
        ".json",
        ".md",
        ".py",
        ".sh",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    }
)
TEXT_NAMES = frozenset({".env"})
MAX_FILE_BYTES = 1_000_000


@dataclass(frozen=True)
class ProjectFile:
    path: str
    text: str

    @cached_property
    def lines(self) -> list[str]:
        return self.text.splitlines()

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def folder(self) -> str:
        return self.path.rpartition("/")[0]

    def find_line(self, text: str, after: int = 0) -> int | None:
        """Return the first line past `after` that contains the text."""
        for number, line in enumerate(self.lines, start=1):
            if number > after and text in line:
                return number
        return None


@dataclass(frozen=True)
class Project:
    root: Path
    files: tuple[ProjectFile, ...]
    not_read: tuple[NotChecked, ...]

    @cached_property
    def paths(self) -> frozenset[str]:
        """Every path that exists in the project, read or not."""
        return frozenset(
            [file.path for file in self.files] + [item.what for item in self.not_read]
        )

    def exists(self, path: str) -> bool:
        """Say whether the path is a file or a folder of the project."""
        prefix = path.rstrip("/") + "/"
        return path in self.paths or any(p.startswith(prefix) for p in self.paths)

    def file(self, path: str) -> ProjectFile | None:
        return next((file for file in self.files if file.path == path), None)

    def named(self, *names: str) -> list[ProjectFile]:
        return [file for file in self.files if file.name in names]

    def with_suffix(self, suffix: str) -> list[ProjectFile]:
        return [file for file in self.files if file.path.endswith(suffix)]


def _read(path: Path, root: Path) -> ProjectFile | NotChecked:
    relative = path.relative_to(root).as_posix()
    if path.is_symlink() and not path.resolve().is_relative_to(root):
        return NotChecked(relative, "symlink_outside")
    if path.suffix not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
        return NotChecked(relative, "file_type")
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return NotChecked(relative, "too_large")
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return NotChecked(relative, "not_text")
    except OSError:
        return NotChecked(relative, "unreadable")
    if "\x00" in text:
        return NotChecked(relative, "not_text")
    return ProjectFile(relative, text)


def load_project(root: Path) -> Project:
    """Read every text file of the project, in a fixed order."""
    root = root.resolve()
    files = []
    not_read = []
    for folder, folder_names, file_names in os.walk(root):
        kept = []
        for name in sorted(folder_names):
            path = Path(folder, name)
            if path.is_symlink():
                not_read.append(
                    NotChecked(path.relative_to(root).as_posix(), "symlinked_folder")
                )
            elif name not in SKIPPED_FOLDERS:
                kept.append(name)
        folder_names[:] = kept
        for name in sorted(file_names):
            result = _read(Path(folder, name), root)
            if isinstance(result, ProjectFile):
                files.append(result)
            else:
                not_read.append(result)
    return Project(root, tuple(files), tuple(not_read))
