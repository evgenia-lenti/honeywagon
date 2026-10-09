"""Decide what kinds of agentic artifact a project contains, from its files."""

import ast

from honeywagon.files import Project
from honeywagon.models import NotChecked

PLUGIN_MANIFEST = ".claude-plugin/plugin.json"
SKILL_FILE = "SKILL.md"
MCP_SERVER_PACKAGES = frozenset({"mcp", "fastmcp"})
AGENT_PACKAGES = frozenset({"claude_agent_sdk"})


def imported_packages(source: str) -> set[str]:
    """Return the top-level packages that a Python file imports."""
    packages: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            packages.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            packages.add(node.module.split(".")[0])
    return packages


def detect(project: Project) -> tuple[tuple[str, ...], tuple[NotChecked, ...]]:
    """Return the kinds found, and the Python files that could not be parsed.

    A project can have more than one kind. A plugin manifest takes priority
    over SKILL.md: skills inside a plugin are part of the plugin.
    """
    kinds = set()
    not_parsed = []
    if project.file(PLUGIN_MANIFEST):
        kinds.add("plugin")
    elif project.named(SKILL_FILE):
        kinds.add("skill")
    for file in project.with_suffix(".py"):
        try:
            packages = imported_packages(file.text)
        except (SyntaxError, ValueError):
            not_parsed.append(NotChecked(file.path, "invalid_python"))
            continue
        if packages & MCP_SERVER_PACKAGES:
            kinds.add("mcp_server")
        if packages & AGENT_PACKAGES:
            kinds.add("agent")
    return tuple(sorted(kinds)), tuple(not_parsed)
