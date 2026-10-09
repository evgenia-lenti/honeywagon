from collections.abc import Callable
from pathlib import Path

import pytest

from honeywagon.files import Project, load_project

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_NAMES = sorted(
    path.parent.name for path in FIXTURES_DIR.glob("*/expected.json")
)

ProjectMaker = Callable[[dict[str, str]], Project]


def fixture_project(name: str) -> Path:
    return FIXTURES_DIR / name / "project"


@pytest.fixture
def make_project(tmp_path: Path) -> ProjectMaker:
    """Build a small project in a temporary folder from {path: content}."""

    def make(files: dict[str, str]) -> Project:
        for path, content in files.items():
            target = tmp_path / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return load_project(tmp_path)

    return make
