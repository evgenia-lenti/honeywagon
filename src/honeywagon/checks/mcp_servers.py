"""MCP servers that the project starts."""

import json
from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.checks.registry import Hit, register
from honeywagon.deps.manifests import launched_package, split_version


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
