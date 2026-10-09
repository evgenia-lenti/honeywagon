import json
from pathlib import Path

import pytest

import evaluate
from evaluate import Expected, Finding, Fixture


def planted(check_id: str, line: int, layer: str = "deterministic") -> Expected:
    return Expected(
        check_id=check_id,
        file="SKILL.md",
        line=line,
        severity="error",
        layer=layer,
        contains="",
    )


def fixture(*expected: Expected, kind: str = "skill") -> Fixture:
    return Fixture(
        name="sample", project_kind=kind, project_dir=Path("project"), expected=expected
    )


def test_no_findings_counts_every_planted_mistake_as_missed() -> None:
    sample = fixture(planted("perm-broad-bash", 4), planted("secret-in-file", 17))

    result = evaluate.evaluate_fixture(sample, [])

    assert result.found == ()
    assert result.false == ()
    assert result.missed == sample.expected


def test_finding_on_the_same_line_is_found() -> None:
    sample = fixture(planted("perm-broad-bash", 4))

    result = evaluate.evaluate_fixture(
        sample, [Finding("perm-broad-bash", "SKILL.md", 4)]
    )

    assert result.found == sample.expected
    assert result.missed == ()
    assert result.false == ()


def test_finding_within_the_line_tolerance_is_found() -> None:
    sample = fixture(planted("perm-broad-bash", 4))
    finding = Finding("perm-broad-bash", "SKILL.md", 4 + evaluate.LINE_TOLERANCE)

    result = evaluate.evaluate_fixture(sample, [finding])

    assert result.found == sample.expected


def test_finding_outside_the_line_tolerance_is_false_and_the_mistake_is_missed() -> (
    None
):
    sample = fixture(planted("perm-broad-bash", 4))
    finding = Finding("perm-broad-bash", "SKILL.md", 4 + evaluate.LINE_TOLERANCE + 1)

    result = evaluate.evaluate_fixture(sample, [finding])

    assert result.missed == sample.expected
    assert result.false == (finding,)


def test_finding_in_another_file_is_false() -> None:
    sample = fixture(planted("perm-broad-bash", 4))
    finding = Finding("perm-broad-bash", "README.md", 4)

    result = evaluate.evaluate_fixture(sample, [finding])

    assert result.false == (finding,)


def test_finding_of_another_check_is_false() -> None:
    sample = fixture(planted("perm-broad-bash", 4))
    finding = Finding("secret-in-file", "SKILL.md", 4)

    result = evaluate.evaluate_fixture(sample, [finding])

    assert result.false == (finding,)


def test_second_finding_for_the_same_mistake_is_false() -> None:
    sample = fixture(planted("perm-broad-bash", 4))
    first = Finding("perm-broad-bash", "SKILL.md", 4)
    second = Finding("perm-broad-bash", "SKILL.md", 5)

    result = evaluate.evaluate_fixture(sample, [first, second])

    assert result.found == sample.expected
    assert result.false == (second,)


def test_any_finding_in_a_fixture_without_mistakes_is_false() -> None:
    finding = Finding("perm-broad-bash", "SKILL.md", 4)

    result = evaluate.evaluate_fixture(fixture(), [finding])

    assert result.false == (finding,)


def test_layer_counts_only_the_mistakes_of_that_layer() -> None:
    by_code = planted("perm-broad-bash", 4)
    by_model = planted("intent-description-mismatch", 3, layer="model")

    result = evaluate.evaluate_fixture(fixture(by_code, by_model), [], "deterministic")

    assert result.missed == (by_code,)


def test_finding_for_a_mistake_of_the_other_layer_is_ignored() -> None:
    by_model = planted("intent-description-mismatch", 3, layer="model")
    finding = Finding("intent-description-mismatch", "SKILL.md", 3)

    result = evaluate.evaluate_fixture(fixture(by_model), [finding], "deterministic")

    assert result.found == ()
    assert result.false == ()


def test_counts_are_split_per_check_and_per_project_kind() -> None:
    skill = fixture(planted("perm-broad-bash", 4), planted("secret-in-file", 17))
    agent = fixture(planted("secret-in-file", 11), kind="agent")
    results = [
        evaluate.evaluate_fixture(skill, [Finding("secret-in-file", "SKILL.md", 17)]),
        evaluate.evaluate_fixture(agent, [Finding("inject-shell", "SKILL.md", 1)]),
    ]

    per_check = evaluate.count_per_check(results)
    per_kind = evaluate.count_per_kind(results)

    assert (per_check["secret-in-file"].found, per_check["secret-in-file"].missed) == (
        1,
        1,
    )
    assert per_check["perm-broad-bash"].missed == 1
    assert per_check["inject-shell"].false == 1
    assert (per_kind["skill"].planted, per_kind["skill"].found) == (2, 1)
    assert (per_kind["agent"].missed, per_kind["agent"].false) == (1, 1)


@pytest.mark.parametrize("wrap", [False, True], ids=["list", "object"])
def test_findings_are_read_from_a_list_or_from_an_object(
    tmp_path: Path, wrap: bool
) -> None:
    entries = [{"check_id": "inject-shell", "file": ".\\src\\server.py", "line": 23}]
    results_file = tmp_path / "sample.json"
    results_file.write_text(json.dumps({"findings": entries} if wrap else entries))

    assert evaluate.load_findings(results_file) == [
        Finding("inject-shell", "src/server.py", 23)
    ]


def test_run_on_an_empty_results_folder_misses_every_planted_mistake(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixtures = evaluate.load_fixtures(evaluate.FIXTURES_DIR)
    planted_total = sum(len(item.expected) for item in fixtures)

    exit_code = evaluate.main(["--results", str(tmp_path)])

    output = capsys.readouterr().out
    missed_lines = output.split("Missed\n")[1].split("\n\n")[0].splitlines()
    assert exit_code == 0
    assert "No results file for:" in output
    assert len(missed_lines) == planted_total
    assert output.rstrip().endswith("False findings\n  (none)")


def test_run_without_results_folder_audits_the_fixtures_with_the_core(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = evaluate.main(["--layer", "deterministic"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "the deterministic core, run now" in output
    assert output.rstrip().endswith("False findings\n  (none)")
