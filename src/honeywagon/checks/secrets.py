"""Keys and tokens written in the project's files."""

import re
from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.checks.registry import Hit, register
from honeywagon.guard.redact import contains_secret, mask

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
    yield from _header_secrets(analysis, options)


def _header_secrets(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    """Find a key written as plain text in a header of a remote MCP server.

    Such a key is known by where it is, not by its shape, so the evidence is
    masked here: the pattern-based redaction would let it through.
    """
    for server in analysis.mcp_servers:
        file = analysis.project.file(server.file)
        assert file is not None
        for name, value in server.headers:
            # A value with ${...} is taken from the environment when it is used.
            if name.lower() not in options["secret_headers"] or "${" in value:
                continue
            words = value.split()
            line = file.find_line(value, server.line - 1) if words else None
            if line is None or contains_secret(file.lines[line - 1]):
                # No value, or a key of a known shape that the loop above reported.
                continue
            # The key is the last word: "Bearer <key>" or the key alone.
            yield Hit(server.file, line, mask(file.lines[line - 1], words[-1]))
