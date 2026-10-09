"""How the project's Python code talks over the network."""

from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.checks.registry import Hit, register


@register("net-tls-off")
def tls_off(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    for module in analysis.python:
        for line in module.tls_off:
            yield Hit(module.file.path, line, module.file.lines[line - 1])
