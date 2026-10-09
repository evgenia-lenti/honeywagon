"""How much an agent or a session may do without asking, and for how long."""

from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.checks.registry import Hit, register


def _line(analysis: Analysis, path: str, number: int) -> str:
    file = analysis.project.file(path)
    assert file is not None
    return file.lines[number - 1]


def _bypass_hit(
    analysis: Analysis, options: Mapping[str, Any], path: str, number: int, mode: Any
) -> Hit | None:
    if not isinstance(mode, str) or mode not in options["bypass_modes"]:
        return None
    line = _line(analysis, path, number)
    return Hit(path, number, line, line.replace(mode, options["safe_mode"]))


@register("perm-bypass-permissions")
def bypass_permissions(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    """The bypass mode in the code of an agent, where it always takes effect."""
    for agent in analysis.agent_options:
        mode = agent.keywords.get("permission_mode")
        hit = mode and _bypass_hit(analysis, options, agent.file, mode.line, mode.value)
        if hit:
            yield hit


@register("perm-bypass-in-settings")
def bypass_in_settings(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    """The bypass mode in a settings file of the project.

    Claude Code 2.1.257 and newer ignore it there, and older versions obey it.
    That is why this is a separate check with a lower severity.
    """
    for setting in analysis.permission_modes:
        hit = _bypass_hit(analysis, options, setting.file, setting.line, setting.mode)
        if hit:
            yield hit


@register("agent-no-turn-limit")
def no_turn_limit(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    for agent in analysis.agent_options:
        # With **settings the limit may be set where the code cannot see it.
        if "max_turns" in agent.keywords or agent.has_unpacked_keywords:
            continue
        yield Hit(agent.file, agent.line, _line(analysis, agent.file, agent.line))
