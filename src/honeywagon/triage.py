"""The risk map: which parts of a project deserve attention first.

It is built from the capability map alone, before any check runs. It is a
guide for attention: it reports no finding and it changes no verdict.
"""

from honeywagon.datafiles import load_data
from honeywagon.models import (
    RISK_TIERS,
    Capability,
    CapabilityMap,
    RiskGroup,
    RiskMap,
    RiskReason,
)

# The kinds of part. A file that is several of them is named after the first.
KINDS = ("agent", "code_tools", "skill", "settings", "hooks", "mcp_servers")
CHANGING_ACTIONS = {"write", "delete", "schema"}


class _Parts:
    """Collects, for each file, its kinds and the reasons to look at it."""

    def __init__(self) -> None:
        self.kinds: dict[str, set[str]] = {}
        self.reasons: dict[str, dict[str, list[str]]] = {}

    def add(self, file: str, kind: str, reason: str, item: str | None = None) -> None:
        self.kinds.setdefault(file, set()).add(kind)
        items = self.reasons.setdefault(file, {}).setdefault(reason, [])
        if item and item not in items:
            items.append(item)


def _tool_reasons(tool: Capability) -> list[str]:
    """Say why a tool written in code deserves attention."""
    scope = tool.data_scope
    reasons = []
    if tool.boundedness == "free_form":
        reasons.append("free_form_input")
    if "shell" in tool.touches:
        reasons.append("runs_commands")
    changes_data = "filesystem_write" in tool.touches or any(
        access.action in CHANGING_ACTIONS for access in scope.tables
    )
    if changes_data:
        reasons.append("changes_data")
    if scope.status == "any":
        reasons.append("data_not_limited")
    if scope.status in ("partial", "unknown"):
        reasons.append("data_access_unknown")
    if "network" in tool.touches:
        reasons.append("uses_network")
    reads_database = scope.status == "known" and not changes_data
    if "filesystem_read" in tool.touches or reads_database:
        reasons.append("reads_data")
    return reasons or ["no_outside_effect"]


def risk_map(capabilities: CapabilityMap) -> RiskMap:
    rules = load_data("risk.toml")
    tiers: dict[str, str] = rules["tiers"]
    agent_files = {agent.declared_in.file for agent in capabilities.agents}
    parts = _Parts()

    for capability in capabilities.capabilities:
        file = capability.declared_in.file
        in_agent = file in agent_files
        if capability.kind == "tool":
            kind = "agent" if in_agent else "code_tools"
            for reason in _tool_reasons(capability):
                parts.add(file, kind, reason, capability.name)
        else:
            any_command = (
                capability.scope == "unrestricted" and "shell" in capability.touches
            )
            reason = "any_command_allowed" if any_command else "allowed_without_asking"
            parts.add(file, "agent" if in_agent else "skill", reason, capability.name)
    for agent in capabilities.agents:
        file = agent.declared_in.file
        parts.add(file, "agent", "runs_an_agent")
        if agent.permission_mode in rules["bypass_modes"]:
            parts.add(file, "agent", "no_permission_prompts", agent.permission_mode)
    for setting in capabilities.permission_modes:
        bypasses = setting.mode in rules["bypass_modes"]
        reason = "no_permission_prompts" if bypasses else "sets_permission_mode"
        parts.add(setting.declared_in.file, "settings", reason, setting.mode)
    for hook in capabilities.hooks:
        parts.add(hook.declared_in.file, "hooks", "runs_by_itself", hook.event)
    for server in capabilities.mcp_servers:
        parts.add(server.declared_in.file, "mcp_servers", "starts_program", server.name)

    order = sorted(tiers, key=lambda key: RISK_TIERS.index(tiers[key]))
    groups = []
    for file, found in parts.reasons.items():
        reasons = tuple(
            RiskReason(key, tiers[key], tuple(found[key]))
            for key in sorted(found, key=order.index)
        )
        groups.append(
            RiskGroup(
                name=file,
                kind=min(parts.kinds[file], key=KINDS.index),
                tier=min((reason.tier for reason in reasons), key=RISK_TIERS.index),
                reasons=reasons,
            )
        )
    groups.sort(key=lambda group: (RISK_TIERS.index(group.tier), group.name))
    return RiskMap(tuple(groups))
