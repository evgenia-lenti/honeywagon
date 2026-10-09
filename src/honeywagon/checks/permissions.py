"""Permissions that a skill gives to Claude."""

import re
from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.checks.registry import Hit, register
from honeywagon.files import Project
from honeywagon.frontmatter import FrontmatterError, frontmatter_values
from honeywagon.models import NotChecked

# One tool name, with its optional rule in parentheses: Read, Bash(git log *).
TOOL = re.compile(r"[^\s,()]+(?:\([^)]*\))?")


@register("perm-broad-bash")
def broad_bash(
    project: Project, options: Mapping[str, Any]
) -> Iterator[Hit | NotChecked]:
    broad_tools = set(options["broad_tools"])
    for file in project.named("SKILL.md"):
        try:
            values = frontmatter_values(file, "allowed-tools")
        except FrontmatterError:
            yield NotChecked(file.path, "invalid_frontmatter")
            continue
        for value in values:
            if broad_tools.intersection(TOOL.findall(value.text)):
                yield Hit(file.path, value.line, file.lines[value.line - 1])
