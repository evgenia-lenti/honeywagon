"""Keys and tokens written in the project's files."""

from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.checks.registry import Hit, register
from honeywagon.files import Project
from honeywagon.guard.redact import contains_secret


@register("secret-in-file")
def secret_in_file(project: Project, options: Mapping[str, Any]) -> Iterator[Hit]:
    for file in project.files:
        for number, line in enumerate(file.lines, start=1):
            if contains_secret(line):
                yield Hit(file.path, number, line)
