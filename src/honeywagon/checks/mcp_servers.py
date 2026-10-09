"""MCP servers that the project starts."""

import json
from collections.abc import Iterator, Mapping
from typing import Any
from urllib.parse import urlsplit

from honeywagon.capability import Analysis
from honeywagon.checks.registry import Hit, register
from honeywagon.deps.manifests import launched_package, split_version
from honeywagon.guard.redact import address


@register("mcp-unpinned-server")
def unpinned_server(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    for server in analysis.mcp_servers:
        launched = launched_package(server)
        if launched is None or split_version(launched[0])[1] is not None:
            continue
        file = analysis.project.file(server.file)
        assert file is not None
        package = launched[0]
        line = file.find_line(json.dumps(package), server.line - 1) or server.line
        yield Hit(server.file, line, file.lines[line - 1])


@register("mcp-plain-http")
def plain_http(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    for server in analysis.mcp_servers:
        # An address that holds a variable cannot be judged from the file.
        if server.url is None or "${" in server.url:
            continue
        parts = urlsplit(server.url)
        host = parts.hostname or ""
        is_local = host in options["local_hosts"] or host.startswith("127.")
        if parts.scheme != "http" or is_local:
            continue
        file = analysis.project.file(server.file)
        assert file is not None
        line = file.find_line(server.url, server.line - 1) or server.line
        evidence = file.lines[line - 1].replace(server.url, address(server.url))
        yield Hit(server.file, line, evidence)
