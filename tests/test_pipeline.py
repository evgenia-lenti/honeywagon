from pathlib import Path

import pytest
from conftest import FIXTURE_NAMES, fixture_project

from honeywagon.pipeline import NOT_COVERED, run_audit
from honeywagon.report import render_json, render_text

FAKE_MARKER = "FAKE-FIXTURE"


def test_skill_fixture_gets_a_partial_not_recommended_verdict() -> None:
    result = run_audit(fixture_project("skill-release-notes"))

    assert result.project_kinds == ("skill",)
    assert result.layers_ran == ("deterministic",)
    assert [f.check_id for f in result.findings] == [
        "perm-broad-bash",
        "secret-in-file",
        "ref-missing-file",
        "port-absolute-path",
    ]
    assert result.verdict.key == "not_recommended"
    assert result.verdict.partial
    assert result.verdict.triggered_by == tuple(
        f.id for f in result.findings if f.severity == "critical"
    )


def test_result_carries_the_capability_map_and_the_suggested_change() -> None:
    result = run_audit(fixture_project("agent-support-triage"))
    bypass = next(f for f in result.findings if f.check_id == "perm-bypass-permissions")

    assert [agent.permission_mode for agent in result.capability_map.agents] == [
        "bypassPermissions"
    ]
    assert bypass.suggestion == 'permission_mode="default",'
    assert bypass.fix_effort == "simple"


def test_findings_carry_evidence_and_come_from_the_deterministic_layer() -> None:
    result = run_audit(fixture_project("skill-release-notes"))
    broad_bash = result.findings[0]

    assert (broad_bash.file, broad_bash.line) == ("SKILL.md", 4)
    assert broad_bash.evidence == "allowed-tools: Bash, Read, Grep"
    assert broad_bash.confidence == "high"
    assert broad_bash.origin.layer == "deterministic"
    assert broad_bash.origin.source == "checks.permissions"
    assert broad_bash.title and broad_bash.consequence


def test_clean_fixture_has_no_findings() -> None:
    result = run_audit(fixture_project("clean-plugin"))

    assert result.findings == ()
    assert result.verdict.key == "no_reason_found"
    assert result.verdict.partial


def test_what_the_layer_does_not_cover_is_always_reported() -> None:
    result = run_audit(fixture_project("clean-plugin"))

    assert {item.reason for item in result.not_checked} >= set(NOT_COVERED)


def test_folder_without_agentic_artifact_is_reported_as_nothing_to_audit(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("# A website")

    result = run_audit(tmp_path)

    assert result.project_kinds == ()
    assert result.layers_ran == ()
    assert result.checks_ran == ()
    assert result.verdict.key == "nothing_to_audit"
    assert result.not_checked[0].reason == "no_agentic_artifact"


def test_the_same_secret_line_twice_gives_two_different_ids(tmp_path: Path) -> None:
    line = "KEY=sk-ant-" + "api03-FAKE-FIXTURE-NOT-A-REAL-KEY\n"
    (tmp_path / "SKILL.md").write_text(f"# x\n{line}\n{line}")

    ids = [finding.id for finding in run_audit(tmp_path).findings]

    assert len(ids) == len(set(ids)) == 2


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_no_secret_reaches_any_output(name: str) -> None:
    result = run_audit(fixture_project(name))

    assert FAKE_MARKER not in render_json(result)
    assert FAKE_MARKER not in render_text(result)


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_the_same_input_gives_the_same_result(name: str) -> None:
    assert run_audit(fixture_project(name)) == run_audit(fixture_project(name))
