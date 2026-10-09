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
    assert output.index("Proposed verdict") < output.index("What this project can do")
    assert output.index("What this project can do") < output.index("Where to look")
    assert output.index("Where to look first") < output.index("Findings")
    assert output.index("Findings") < output.index("Not checked")


def test_text_report_says_which_data_each_tool_reaches(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(fixture_project("mcp-customer-db"))])

    output = capsys.readouterr().out
    assert "data: notes: writes customer_id, note  (database customers.db)" in output
    assert "data: decided by the input, not limited by the code" in output
    assert "fetch_invoice  (server.py:31)  uses the network" in output


def test_text_report_orders_the_parts_by_attention(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main([str(fixture_project("clean-plugin"))])

    output = capsys.readouterr().out
    assert output.index("Look first") < output.index("hooks/hooks.json  (hooks)")
    assert output.index("hooks/hooks.json  (hooks)") < output.index("Look next")
    assert output.index("Look next") < output.index(".mcp.json  (MCP servers)")
    assert "- changes or deletes data: add_note" in output
    assert "data: notes: reads body, id  (database unknown)" in output


def test_folder_with_nothing_to_audit_has_no_risk_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# A website")

    main([str(tmp_path)])

    assert "Where to look first" not in capsys.readouterr().out


def test_clean_project_exits_with_zero(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([str(fixture_project("clean-plugin"))])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Proposed verdict: No reason found not to use" in output
    assert "No findings." in output


def test_json_report_is_the_whole_result(capsys: pytest.CaptureFixture[str]) -> None:
    main([str(fixture_project("plugin-team-helper")), "--format", "json"])

    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == 2
    assert result["project_kinds"] == ["plugin"]
    assert result["verdict"]["key"] == "not_recommended"
    assert {f["check_id"] for f in result["findings"]} == {
        "hook-remote-code",
        "secret-in-file",
        "mcp-unpinned-server",
    }
    servers = [s["name"] for s in result["capability_map"]["mcp_servers"]]
    assert servers == ["issues", "docs"]
    assert result["looked_up"] == []
    assert result["capability_map"]["capabilities"][0]["data_scope"] == {
        "status": "unknown",
        "database": None,
        "database_variable": None,
        "tables": [],
    }
    assert result["risk_map"]["groups"][0] == {
        "name": "hooks/hooks.json",
        "kind": "hooks",
        "tier": "high",
        "reasons": [
            {"key": "runs_by_itself", "tier": "high", "items": ["SessionStart"]}
        ],
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
