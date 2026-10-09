"""Permissions that a skill or an agent gives to Claude."""

from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.checks.registry import Hit, register


@register("perm-broad-bash")
def broad_bash(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    broad_tools = set(options["broad_tools"])
    reported = set()
    for tool in analysis.allowed_tools:
        place = (tool.file, tool.line)
        if tool.name in broad_tools and place not in reported:
            reported.add(place)
            file = analysis.project.file(tool.file)
            assert file is not None
            yield Hit(tool.file, tool.line, file.lines[tool.line - 1])
