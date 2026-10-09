"""Hooks: commands that run by themselves, without asking."""

import json
import re
from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.checks.registry import Hit, register
from honeywagon.files import Project, ProjectFile
from honeywagon.models import NotChecked


def hook_commands(value: Any) -> Iterator[str]:
    """Yield the command of every command hook, wherever it sits in the JSON."""
    if isinstance(value, dict):
        command = value.get("command")
        if value.get("type") == "command" and isinstance(command, str):
            yield command
        for child in value.values():
            yield from hook_commands(child)
    elif isinstance(value, list):
        for child in value:
            yield from hook_commands(child)


def line_of(file: ProjectFile, command: str, after: int) -> int:
    """Find the line that holds the command, looking past lines already used."""
    encoded = json.dumps(command)
    for number, line in enumerate(file.lines, start=1):
        if number > after and encoded in line:
            return number
    return 1


@register("hook-remote-code")
def hook_remote_code(
    project: Project, options: Mapping[str, Any]
) -> Iterator[Hit | NotChecked]:
    patterns = [re.compile(pattern) for pattern in options["patterns"]]
    for file in project.named(*options["files"]):
        try:
            data = json.loads(file.text)
        except json.JSONDecodeError:
            yield NotChecked(file.path, "invalid_json")
            continue
        last_line = 0
        for command in hook_commands(data):
            line = line_of(file, command, last_line)
            last_line = line
            if any(pattern.search(command) for pattern in patterns):
                yield Hit(file.path, line, file.lines[line - 1])
