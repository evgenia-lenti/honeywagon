"""MCP servers that the project starts."""

import json
import re
from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.capability.config_files import McpServer
from honeywagon.checks.registry import Hit, register

EXECUTABLE_SUFFIX = re.compile(r"\.(cmd|exe|bat)$", re.IGNORECASE)


def launched_package(server: McpServer, options: Mapping[str, Any]) -> str | None:
    """Return the package a launcher such as npx downloads and runs, if any."""
    command = EXECUTABLE_SUFFIX.sub("", (server.command or "").rsplit("/", 1)[-1])
    if command not in options["launchers"]:
        return None
    for argument in server.args:
        if not argument.startswith("-") and argument not in options["subcommands"]:
            return argument
    return None


def has_version(package: str) -> bool:
    """Say whether the package names an exact version: name@1.2.3 or name==1.2.3."""
    if "==" in package:
        return True
    version = package[1:].partition("@")[2]
    return bool(version) and version != "latest"


@register("mcp-unpinned-server")
def unpinned_server(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    for server in analysis.mcp_servers:
        package = launched_package(server, options)
        if package is None or has_version(package):
            continue
        file = analysis.project.file(server.file)
        assert file is not None
        line = file.find_line(json.dumps(package), server.line - 1) or server.line
        yield Hit(server.file, line, file.lines[line - 1])
