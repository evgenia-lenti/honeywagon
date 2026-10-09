"""Deterministic checks. Importing this package registers every check."""

from honeywagon.checks import hooks, permissions, secrets
from honeywagon.checks.registry import Check, Hit, load_checks

__all__ = ["Check", "Hit", "hooks", "load_checks", "permissions", "secrets"]
