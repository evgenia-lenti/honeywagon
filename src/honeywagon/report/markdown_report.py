"""The report as Markdown, for a conversation or a document.

It says the same as the text report. Everything that comes from the audited
project is written as code or escaped, so that it can neither change the
layout of the report nor pass for text of the tool.
"""

import re
from itertools import groupby
from typing import Any
from urllib.parse import quote

from honeywagon.datafiles import load_texts
from honeywagon.models import (
    RISK_TIERS,
    SEVERITIES,
    CapabilityMap,
    Finding,
    Location,
    RiskMap,
    RunResult,
)
from honeywagon.report.text_report import MAX_LISTED_PER_REASON, describe_data

MARKDOWN_SIGNS = re.compile(r"([\\`*_\[\]<>|#~])")
BACKTICKS = re.compile(r"`+")


def plain(text: str) -> str:
    """Escape the signs that Markdown would read as formatting."""
    return MARKDOWN_SIGNS.sub(r"\\\1", text)


def _longest_backtick_run(text: str) -> int:
    return max((len(run) for run in BACKTICKS.findall(text)), default=0)


def code(text: str) -> str:
    """Write a text from the project as inline code, whatever it contains."""
    text = " ".join(text.split()) or " "
    fence = "`" * (_longest_backtick_run(text) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def code_list(items: tuple[str, ...]) -> str:
    return ", ".join(code(item) for item in items)


def link(file: str, line: int | None = None) -> str:
    """Link to a file of the audited project, and to a line when one is given."""
    label = f"{file}:{line}" if line else file
    anchor = f"#L{line}" if line else ""
    return f"[{code(label)}]({quote(file, safe='/')}{anchor})"


def _place(location: Location) -> str:
    return link(location.file, location.line)


def _capabilities(capabilities: CapabilityMap, texts: dict[str, Any]) -> list[str]:
    labels = texts["capabilities"]
    lines = [f"## {labels['title']}", ""]
    allowed = [c for c in capabilities.capabilities if c.kind == "allowed_tool"]
    tools = [c for c in capabilities.capabilities if c.kind == "tool"]
    start = len(lines)

    if allowed:
        lines += [f"**{labels['allowed_tools']}**", ""]
        for tool in allowed:
            scope = "restricted" if tool.scope == "restricted" else "any_use"
            where = _place(tool.declared_in)
            lines.append(f"- {code(tool.name)} ({where}): {labels[scope]}")
        lines.append("")
    if tools:
        lines += [f"**{labels['tools']}**", ""]
        for tool in tools:
            touches = [texts["touches"][touch] for touch in tool.touches]
            what = ", ".join(touches) or labels["touches_nothing"]
            how = texts["boundedness"][tool.boundedness]
            where = _place(tool.declared_in)
            lines.append(f"- {code(tool.name)} ({where}): {what}; {how}")
            if tool.data_scope.status != "none":
                lines.append(f"  - {plain(describe_data(tool.data_scope, texts))}")
        lines.append("")
    if capabilities.mcp_servers:
        lines += [f"**{labels['mcp_servers']}**", ""]
        for server in capabilities.mcp_servers:
            where = _place(server.declared_in)
            lines.append(f"- {code(server.name)} ({where}): {code(server.command)}")
        lines.append("")
    if capabilities.hooks:
        lines += [f"**{labels['hooks']}**", ""]
        for hook in capabilities.hooks:
            where = _place(hook.declared_in)
            lines.append(f"- {code(hook.event)} ({where}): {code(hook.command)}")
        lines.append("")
    if capabilities.agents:
        lines += [f"**{labels['agents']}**", ""]
        for agent in capabilities.agents:
            known = agent.permission_mode
            mode = code(known) if known else labels["not_set"]
            limit = {True: "yes", False: "no", None: "unknown"}[agent.has_turn_limit]
            lines.append(
                f"- {_place(agent.declared_in)}: {labels['permission_mode']}: "
                f"{mode}; {labels['turn_limit']}: {labels[limit]}"
            )
        lines.append("")
    if capabilities.permission_modes:
        lines += [f"**{labels['permission_modes']}**", ""]
        for setting in capabilities.permission_modes:
            lines.append(f"- {code(setting.mode)} ({_place(setting.declared_in)})")
        lines.append("")
    if len(lines) == start:
        lines += [labels["nothing"], ""]
    return lines


def _risks(risks: RiskMap, texts: dict[str, Any]) -> list[str]:
    lines = [f"## {texts['risk']['title']}", "", f"*{texts['risk']['intro']}*", ""]
    for tier in RISK_TIERS:
        groups = [group for group in risks.groups if group.tier == tier]
        if not groups:
            continue
        lines += [f"**{texts['risk_tiers'][tier]}**", ""]
        for group in groups:
            kind = texts["risk_kinds"][group.kind]
            lines.append(f"- {link(group.name)} ({kind})")
            for reason in group.reasons:
                text = texts["risk_reasons"][reason.key]
                items = f": {code_list(reason.items)}" if reason.items else ""
                lines.append(f"  - {text}{items}")
        lines.append("")
    return lines


def _finding(finding: Finding, labels: dict[str, Any]) -> list[str]:
    fence = "`" * max(3, _longest_backtick_run(finding.evidence) + 1)
    lines = [
        f"- **{finding.title}**",
        "",
        f"  {link(finding.file, finding.line)} · {code(finding.id)} · "
        f"{labels['confidence']}: {finding.confidence} · "
        f"{labels['fix']}: {finding.fix_effort}",
        "",
        f"  {fence}text",
        f"  {finding.evidence}",
        f"  {fence}",
        "",
        f"  {plain(finding.consequence)}",
        "",
    ]
    if finding.suggestion:
        lines += [f"  {labels['suggested_change']}: {code(finding.suggestion)}", ""]
    return lines


def render_markdown(result: RunResult, language: str = "en") -> str:
    texts = load_texts(language)
    labels = texts["report"]
    none = labels["none"]
    lines = [f"# {labels['title']}", "", f"*{labels['advisory']}*", ""]

    lines += [f"**{labels['proposed_verdict']}: {result.verdict.text}**", ""]
    if result.verdict.partial:
        lines += [labels["partial"], ""]
    if result.verdict.triggered_by:
        reasons = code_list(result.verdict.triggered_by)
        lines += [f"{labels['because_of']}: {reasons}", ""]

    kinds = ", ".join(texts["kinds"][kind] for kind in result.project_kinds)
    lines += [
        f"- {labels['project_kinds']}: {kinds or none}",
        f"- {labels['layers_ran']}: {', '.join(result.layers_ran) or none}",
        f"- {labels['checks_ran']}: {', '.join(result.checks_ran) or none}",
    ]
    if result.looked_up:
        lines.append(f"- {labels['looked_up']}: {code_list(result.looked_up)}")
    lines.append("")

    if result.project_kinds:
        lines += _capabilities(result.capability_map, texts)
    if result.risk_map.groups:
        lines += _risks(result.risk_map, texts)

    lines += [f"## {labels['findings']}", ""]
    if not result.findings:
        lines += [labels["no_findings"], ""]
    for severity in SEVERITIES:
        findings = [f for f in result.findings if f.severity == severity]
        if not findings:
            continue
        lines += [f"### {texts['severity'][severity]}", ""]
        for finding in findings:
            lines += _finding(finding, labels)

    lines += [f"## {labels['not_checked']}", ""]
    by_reason = sorted(result.not_checked, key=lambda item: item.reason)
    for reason, group in groupby(by_reason, key=lambda item: item.reason):
        items = [plain(item.what) for item in group]
        listed = items[:MAX_LISTED_PER_REASON]
        if len(items) > len(listed):
            listed.append(labels["more_files"].format(count=len(items) - len(listed)))
        lines.append(f"- **{', '.join(listed)}**: {texts['not_checked'][reason]}")
    return "\n".join(lines) + "\n"
