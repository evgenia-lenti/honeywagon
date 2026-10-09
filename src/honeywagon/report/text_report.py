"""The report a person reads: verdict, what the project can do, findings, gaps."""

from itertools import groupby
from typing import Any

from honeywagon.datafiles import load_texts
from honeywagon.models import SEVERITIES, CapabilityMap, Location, RunResult

# Files that were not read are listed up to this number, then counted.
MAX_LISTED_PER_REASON = 10


def _place(location: Location) -> str:
    return f"{location.file}:{location.line}"


def _capabilities(capabilities: CapabilityMap, texts: dict[str, Any]) -> list[str]:
    labels = texts["capabilities"]
    lines = [labels["title"]]
    allowed = [c for c in capabilities.capabilities if c.kind == "allowed_tool"]
    tools = [c for c in capabilities.capabilities if c.kind == "tool"]

    if allowed:
        lines.append(f"  {labels['allowed_tools']}")
        for tool in allowed:
            scope = "restricted" if tool.scope == "restricted" else "any_use"
            lines.append(
                f"    {tool.name}  ({_place(tool.declared_in)})  {labels[scope]}"
            )
    if tools:
        lines.append(f"  {labels['tools']}")
        for tool in tools:
            touches = [texts["touches"][touch] for touch in tool.touches]
            what = ", ".join(touches) or labels["touches_nothing"]
            how = texts["boundedness"][tool.boundedness]
            lines.append(
                f"    {tool.name}  ({_place(tool.declared_in)})  {what}; {how}"
            )
    if capabilities.mcp_servers:
        lines.append(f"  {labels['mcp_servers']}")
        for server in capabilities.mcp_servers:
            lines.append(
                f"    {server.name}  ({_place(server.declared_in)})  {server.command}"
            )
    if capabilities.hooks:
        lines.append(f"  {labels['hooks']}")
        for hook in capabilities.hooks:
            lines.append(
                f"    {hook.event}  ({_place(hook.declared_in)})  {hook.command}"
            )
    if capabilities.agents:
        lines.append(f"  {labels['agents']}")
        for agent in capabilities.agents:
            mode = agent.permission_mode or labels["not_set"]
            limit = {True: "yes", False: "no", None: "unknown"}[agent.has_turn_limit]
            lines.append(
                f"    ({_place(agent.declared_in)})  {labels['permission_mode']}: "
                f"{mode}; {labels['turn_limit']}: {labels[limit]}"
            )
    if capabilities.permission_modes:
        lines.append(f"  {labels['permission_modes']}")
        for setting in capabilities.permission_modes:
            lines.append(f"    {setting.mode}  ({_place(setting.declared_in)})")
    if len(lines) == 1:
        lines.append(f"  {labels['nothing']}")
    return lines


def render_text(result: RunResult, language: str = "en") -> str:
    texts = load_texts(language)
    labels = texts["report"]
    none = labels["none"]
    lines = [labels["title"], labels["advisory"], ""]
    kinds = ", ".join(texts["kinds"][kind] for kind in result.project_kinds)
    lines.append(f"{labels['project_kinds']}: {kinds or none}")
    lines.append(f"{labels['layers_ran']}: {', '.join(result.layers_ran) or none}")
    lines.append(f"{labels['checks_ran']}: {', '.join(result.checks_ran) or none}")

    lines += ["", f"{labels['proposed_verdict']}: {result.verdict.text}"]
    if result.verdict.partial:
        lines.append(labels["partial"])
    if result.verdict.triggered_by:
        lines.append(
            f"{labels['because_of']}: {', '.join(result.verdict.triggered_by)}"
        )

    if result.project_kinds:
        lines += ["", *_capabilities(result.capability_map, texts)]

    lines += ["", labels["findings"]]
    if not result.findings:
        lines.append(f"  {labels['no_findings']}")
    for severity in SEVERITIES:
        findings = [f for f in result.findings if f.severity == severity]
        if not findings:
            continue
        lines += ["", f"  {texts['severity'][severity]}"]
        for finding in findings:
            lines += [
                f"    {finding.title}",
                f"      {finding.file}:{finding.line}  [{finding.id}]  "
                f"{labels['confidence']}: {finding.confidence}  "
                f"{labels['fix']}: {finding.fix_effort}",
                f"      > {finding.evidence}",
                f"      {finding.consequence}",
            ]
            if finding.suggestion:
                lines.append(
                    f"      {labels['suggested_change']}: {finding.suggestion}"
                )

    lines += ["", labels["not_checked"]]
    by_reason = sorted(result.not_checked, key=lambda item: item.reason)
    for reason, group in groupby(by_reason, key=lambda item: item.reason):
        items = [item.what for item in group]
        listed = items[:MAX_LISTED_PER_REASON]
        if len(items) > len(listed):
            listed.append(labels["more_files"].format(count=len(items) - len(listed)))
        lines.append(f"  - {', '.join(listed)}: {texts['not_checked'][reason]}")
    return "\n".join(lines)
