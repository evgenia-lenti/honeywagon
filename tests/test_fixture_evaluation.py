"""The deterministic core measured against the fixtures, on every test run."""

import pytest

import evaluate
from evaluate import Fixture
from honeywagon.checks import load_checks

FIXTURES = evaluate.load_fixtures(evaluate.FIXTURES_DIR)
BUILT_CHECKS = {check.check_id for check in load_checks()}


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fixture: fixture.name)
def test_core_reports_no_false_finding(fixture: Fixture) -> None:
    result = evaluate.evaluate_fixture(fixture, evaluate.run_core(fixture))

    assert result.false == ()


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fixture: fixture.name)
def test_core_finds_every_planted_mistake_of_the_checks_that_exist(
    fixture: Fixture,
) -> None:
    result = evaluate.evaluate_fixture(fixture, evaluate.run_core(fixture))

    assert [e for e in result.missed if e.check_id in BUILT_CHECKS] == []


# Checks that have unit tests but no planted mistake yet. Each one is a row in
# docs/known-gaps.md. Remove a check from here when a fixture exercises it.
WITHOUT_FIXTURE = {"perm-bypass-in-settings"}


def test_every_built_check_is_exercised_by_a_fixture() -> None:
    planted = {
        expected.check_id for fixture in FIXTURES for expected in fixture.expected
    }

    assert BUILT_CHECKS - planted == WITHOUT_FIXTURE
