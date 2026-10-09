"""Hooks: commands that run by themselves, without asking."""

import re
from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.checks.registry import Hit, register


@register("hook-remote-code")
def hook_remote_code(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    patterns = [re.compile(pattern) for pattern in options["patterns"]]
    for hook in analysis.hooks:
        if any(pattern.search(hook.command) for pattern in patterns):
            file = analysis.project.file(hook.file)
            assert file is not None
            yield Hit(hook.file, hook.line, file.lines[hook.line - 1])
