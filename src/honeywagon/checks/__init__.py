"""Deterministic checks. Importing this package registers every check."""

from honeywagon.checks import (
    agents,
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
