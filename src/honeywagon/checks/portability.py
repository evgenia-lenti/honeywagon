"""Things that work only on the computer of whoever wrote them."""

import re
from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.checks.registry import Hit, register


@register("port-absolute-path")
def absolute_path(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    patterns = [re.compile(pattern) for pattern in options["patterns"]]
    placeholders = {name.lower() for name in options["placeholder_names"]}
    for file in analysis.project.files:
        for number, line in enumerate(file.lines, start=1):
            users = [m.group("user") for p in patterns for m in p.finditer(line)]
            if any(user.lower() not in placeholders for user in users):
                yield Hit(file.path, number, line)
