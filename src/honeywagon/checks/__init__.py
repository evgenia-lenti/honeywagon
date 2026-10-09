"""Deterministic checks. Importing this package registers every check."""

from honeywagon.checks import (
    agents,
    dependencies,
    hooks,
    mcp_servers,
    permissions,
    portability,
    project_tests,
    references,
    secrets,
    tools,
)
from honeywagon.checks.registry import Check, Hit, load_checks

__all__ = [
    "Check",
    "Hit",
    "agents",
    "dependencies",
    "hooks",
    "load_checks",
    "mcp_servers",
    "permissions",
    "portability",
    "project_tests",
    "references",
    "secrets",
    "tools",
]
