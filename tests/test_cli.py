import json
from pathlib import Path

import pytest
from conftest import fixture_project

from honeywagon.cli import main


def test_text_report_starts_with_the_verdict_and_ends_with_not_checked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main([str(fixture_project("skill-release-notes"))])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Proposed verdict: Not recommended for use" in output
    assert "Partial:" in output
    assert "SKILL.md:4" in output
    assert "sk-ant...REDACTED" in output
    assert output.index("Proposed verdict") < output.index("Findings")
    assert output.index("Findings") < output.index("Not checked")


def test_clean_project_exits_with_zero(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([str(fixture_project("clean-plugin"))])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Proposed verdict: No reason found not to use" in output
    assert "No findings." in output


def test_json_report_is_the_whole_result(capsys: pytest.CaptureFixture[str]) -> None:
    main([str(fixture_project("plugin-team-helper")), "--format", "json"])

    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == 1
    assert result["project_kinds"] == ["plugin"]
    assert result["verdict"]["key"] == "not_recommended"
    assert {f["check_id"] for f in result["findings"]} == {
        "hook-remote-code",
        "secret-in-file",
    }
    assert set(result["findings"][0]) == {
        "id",
        "check_id",
        "title",
        "file",
        "line",
        "evidence",
        "consequence",
        "severity",
        "confidence",
        "fix_effort",
        "suggestion",
        "origin",
        "verification",
    }


def test_folder_that_does_not_exist_is_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as error:
        main([str(tmp_path / "missing")])

    assert error.value.code == 2
