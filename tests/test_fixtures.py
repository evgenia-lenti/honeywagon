import json
import re

import pytest

import evaluate
from evaluate import Expected, Fixture

FIXTURES = evaluate.load_fixtures(evaluate.FIXTURES_DIR)
PLANTED = [(item, expected) for item in FIXTURES for expected in item.expected]

PROJECT_KINDS = {"skill", "plugin", "mcp_server", "agent"}
SEVERITIES = {"critical", "error", "warning", "suggestion", "nitpick"}
SECRET_PREFIXES = ("sk-", "ghp_", "xoxb-")


def fixture_id(item: Fixture) -> str:
    return item.name


def planted_id(pair: tuple[Fixture, Expected]) -> str:
    item, expected = pair
    return f"{item.name}:{expected.check_id}"


def test_every_project_kind_has_a_fixture_with_mistakes() -> None:
    assert {item.project_kind for item in FIXTURES if item.expected} == PROJECT_KINDS


def test_there_is_a_fixture_without_mistakes() -> None:
    assert [item.name for item in FIXTURES if not item.expected] == ["clean-plugin"]


@pytest.mark.parametrize("item", FIXTURES, ids=fixture_id)
def test_fixture_is_well_formed(item: Fixture) -> None:
    data = json.loads((item.project_dir.parent / "expected.json").read_text("utf-8"))

    assert data["schema_version"] == 1
    assert item.project_kind in PROJECT_KINDS
    assert item.project_dir.is_dir()
    assert not list(item.project_dir.rglob("expected.json"))


@pytest.mark.parametrize("item", [f for f in FIXTURES if f.expected], ids=fixture_id)
def test_fixture_has_three_to_five_distinct_mistakes(item: Fixture) -> None:
    places = {(e.check_id, e.file, e.line) for e in item.expected}

    assert 3 <= len(item.expected) <= 5
    assert len(places) == len(item.expected)


@pytest.mark.parametrize("pair", PLANTED, ids=planted_id)
def test_planted_mistake_has_valid_fields(pair: tuple[Fixture, Expected]) -> None:
    _, expected = pair

    assert re.fullmatch(r"[a-z]+(-[a-z]+)+", expected.check_id)
    assert expected.severity in SEVERITIES
    assert expected.layer in evaluate.LAYERS
    assert expected.file == evaluate.normalise_path(expected.file)
    assert expected.contains


@pytest.mark.parametrize("pair", PLANTED, ids=planted_id)
def test_planted_mistake_points_at_its_line(pair: tuple[Fixture, Expected]) -> None:
    item, expected = pair
    lines = (item.project_dir / expected.file).read_text("utf-8").splitlines()

    assert 1 <= expected.line <= len(lines)
    assert expected.contains in lines[expected.line - 1]


@pytest.mark.parametrize("pair", PLANTED, ids=planted_id)
def test_expected_file_never_repeats_a_secret(pair: tuple[Fixture, Expected]) -> None:
    _, expected = pair

    assert not any(prefix in expected.contains for prefix in SECRET_PREFIXES)
