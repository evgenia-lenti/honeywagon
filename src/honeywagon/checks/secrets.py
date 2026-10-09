"""Keys and tokens written in the project's files."""

import re
from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.checks.registry import Hit, register
from honeywagon.guard.redact import contains_secret

# A JSON line that gives a name its value: "API_KEY": "the-key",
JSON_ENTRY = re.compile(r'^\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*:\s*"[^"]*"(,?)\s*$')


def environment_reference(line: str) -> str | None:
    """Return the JSON line with the key taken from an environment variable."""
    match = JSON_ENTRY.match(line)
    if match is None:
        return None
    name, comma = match.groups()
    return f'"{name}": "${{{name}}}"{comma}'


@register("secret-in-file")
def secret_in_file(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    for file in analysis.project.files:
        for number, line in enumerate(file.lines, start=1):
            if not contains_secret(line):
                continue
            is_json = file.path.endswith(".json")
            suggestion = environment_reference(line) if is_json else None
            yield Hit(file.path, number, line, suggestion)
