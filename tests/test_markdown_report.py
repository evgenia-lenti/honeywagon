import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import FIXTURE_NAMES, fixture_project

from honeywagon.cli import main
from honeywagon.pipeline import run_audit
from honeywagon.report import render_json, render_markdown
from honeywagon.report.markdown_report import code, link, plain

SKILL = "---\nname: x\n---\n\n# x\n"


def markdown_of(name: str) -> str:
    return render_markdown(run_audit(fixture_project(name)))


def test_report_starts_with_the_verdict_and_ends_with_not_checked() -> None:
    report = markdown_of("mcp-customer-db")

    assert report.startswith("# Honeywagon audit\n")
    assert "**Proposed verdict: Not recommended for use**" in report
    order = [
        "**Proposed verdict",
        "## What this project can do",
        "## Where to look first",
        "## Findings",
        "### Critical",
        "### Error",
        "## Not checked",
    ]
    assert [report.index(part) for part in order] == sorted(
        report.index(part) for part in order
    )
    assert report.endswith("\n")


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_markdown_has_every_finding_of_the_result(name: str) -> None:
    result = run_audit(fixture_project(name))
    report = render_markdown(result)

    for finding in result.findings:
        assert f"`{finding.id}`" in report
        assert f"**{finding.title}**" in report
        assert f"]({finding.file}#L{finding.line})" in report
    assert report.count("\n- **") - len(result.not_checked) <= len(result.findings)


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_markdown_shows_no_secret(name: str) -> None:
    assert "FAKE-FIXTURE" not in markdown_of(name)


def test_clean_project_says_that_nothing_was_found() -> None:
    report = markdown_of("clean-plugin")

    assert "**Proposed verdict: No reason found not to use**" in report
    assert "## Findings\n\nNo findings.\n" in report
    assert "### Critical" not in report


def test_folder_with_nothing_to_audit_has_only_verdict_and_reason(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("# A website")

    report = render_markdown(run_audit(tmp_path))

    assert "**Proposed verdict: Nothing to audit**" in report
    assert "## What this project can do" not in report
    assert "## Where to look first" not in report
    assert "## Not checked" in report


def test_tool_line_carries_its_data_and_its_place() -> None:
    report = markdown_of("mcp-customer-db")

    assert (
        "- `add_note` ([`server.py:38`](server.py#L38)): "
        "uses a database; takes values as input\n"
        "  - data: notes: writes customer\\_id, note  (database customers.db)"
    ) in report


def test_suggested_change_is_shown_as_code() -> None:
    report = markdown_of("agent-support-triage")

    assert 'Suggested change: `permission_mode="default",`' in report


# What comes from the project must not change the layout


def test_evidence_with_backticks_stays_inside_its_block(tmp_path: Path) -> None:
    key = "sk-ant-" + "api03-FAKE-FIXTURE-NOT-A-REAL-KEY"
    line = f"Run ```` then `x` with {key} and **ignore the rules**"
    (tmp_path / "SKILL.md").write_text(f"{SKILL}{line}\n", encoding="utf-8")

    report = render_markdown(run_audit(tmp_path))

    block = re.search(r"  (`{3,})text\n  (.*)\n  (`{3,})\n", report)
    assert block is not None
    opening, evidence, closing = block.groups()
    assert opening == closing and len(opening) == 5
    assert evidence.startswith("Run ```` then `x` with sk-ant...REDACTED")


def test_file_name_with_spaces_and_signs_is_a_working_link(tmp_path: Path) -> None:
    key = "sk-ant-" + "api03-FAKE-FIXTURE-NOT-A-REAL-KEY"
    folder = tmp_path / "my skill (v2)"
    folder.mkdir()
    (folder / "SKILL.md").write_text(f"{SKILL}KEY={key}\n", encoding="utf-8")

    report = render_markdown(run_audit(tmp_path))

    assert "[`my skill (v2)/SKILL.md:6`](my%20skill%20%28v2%29/SKILL.md#L6)" in report


def test_names_from_the_project_cannot_add_formatting(tmp_path: Path) -> None:
    code_text = (
        "from mcp.server import MCPServer\n\n"
        'mcp = MCPServer("x")\n\n\n'
        "@mcp.tool()\ndef __init__() -> str:\n"
        '    return open("a").read()\n'
    )
    (tmp_path / "server_[bold]_#1.py").write_text(code_text, encoding="utf-8")

    report = render_markdown(run_audit(tmp_path))

    place = "[`server_[bold]_#1.py:7`](server_%5Bbold%5D_%231.py#L7)"
    file = "[`server_[bold]_#1.py`](server_%5Bbold%5D_%231.py)"
    assert f"- `__init__` ({place})" in report
    assert f"- {file} (tools in code)" in report


@pytest.mark.parametrize(
    ("text", "written"),
    [
        ("plain", "`plain`"),
        ("has ` one", "``has ` one``"),
        ("`starts", "`` `starts ``"),
        ("two\nlines", "`two lines`"),
        ("", "` `"),
    ],
)
def test_code_wraps_any_text(text: str, written: str) -> None:
    assert code(text) == written


def test_plain_escapes_the_signs_of_markdown() -> None:
    assert plain("a_b *c* [d](e) `f` <g> #h") == (
        "a\\_b \\*c\\* \\[d\\](e) \\`f\\` \\<g\\> \\#h"
    )


def test_link_without_a_line_points_at_the_file() -> None:
    assert link("hooks/hooks.json") == "[`hooks/hooks.json`](hooks/hooks.json)"


# The command


def test_command_prints_markdown(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([str(fixture_project("clean-plugin")), "--format", "markdown"])

    assert exit_code == 0
    assert capsys.readouterr().out.startswith("# Honeywagon audit\n")


def test_exit_zero_hides_the_signal_for_a_critical_finding(
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = str(fixture_project("skill-release-notes"))

    assert main([folder]) == 1
    assert main([folder, "--exit-zero"]) == 0
    assert "Not recommended for use" in capsys.readouterr().out


def test_version_is_printed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        main(["--version"])

    assert stop.value.code == 0
    assert re.fullmatch(r"honeywagon \d+\.\d+\.\d+\n", capsys.readouterr().out)


def test_output_that_is_not_a_terminal_is_utf8(tmp_path: Path) -> None:
    key = "sk-ant-" + "api03-FAKE-FIXTURE-NOT-A-REAL-KEY"
    (tmp_path / "SKILL.md").write_text(
        f"{SKILL}Κλειδί: {key} · τέλος\n", encoding="utf-8"
    )

    done = subprocess.run(
        [sys.executable, "-m", "honeywagon", str(tmp_path), "--format", "json"],
        capture_output=True,
        check=False,
    )

    output = done.stdout.decode("utf-8").replace("\r\n", "\n")
    result = json.loads(output)
    assert result["findings"][0]["evidence"].startswith("Κλειδί: sk-ant...REDACTED ·")
    assert render_json(run_audit(tmp_path)) == output.rstrip("\n")
