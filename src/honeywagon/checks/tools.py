"""Tools written in Python, in an MCP server or an agent."""

from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.capability.python_code import INPUT_NONE, INPUT_WHOLE, PythonTool
from honeywagon.checks.registry import Hit, register


def _hit(analysis: Analysis, tool: PythonTool, line: int) -> Hit:
    file = analysis.project.file(tool.file)
    assert file is not None
    return Hit(tool.file, line, file.lines[line - 1])


@register("inject-shell")
def shell_injection(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    for tool in analysis.tools:
        for effect in tool.effects:
            reaches_shell = effect.touch == "shell" and effect.through_shell
            if reaches_shell and effect.input != INPUT_NONE:
                yield _hit(analysis, tool, effect.argument_line)


@register("tool-free-form-sql")
def free_form_sql(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    for tool in analysis.tools:
        if any(e.touch == "database" and e.input == INPUT_WHOLE for e in tool.effects):
            yield _hit(analysis, tool, tool.line)


@register("mcp-fetch-any-url")
def fetch_any_url(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    for tool in analysis.tools:
        for effect in tool.effects:
            if effect.touch == "network" and effect.input == INPUT_WHOLE:
                yield _hit(analysis, tool, effect.argument_line)
