"""Where the project's own tests run."""

import ast
import re
from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.checks.registry import Hit, register

TEST_FILE = re.compile(r"(^|/)(tests?/.*|test_[^/]*|[^/]*_test)\.py$")


def is_temporary(target: ast.expr | None, temporary_names: set[str]) -> bool:
    """Say whether a database target is in memory or in a temporary folder."""
    if target is None:
        return True
    if isinstance(target, ast.Constant):
        return target.value == ":memory:"
    names = {node.id for node in ast.walk(target) if isinstance(node, ast.Name)}
    return bool(names & temporary_names)


@register("test-real-database")
def real_database(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    temporary_names = set(options["temporary_names"])
    for module in analysis.python:
        if not TEST_FILE.search(module.file.path):
            continue
        for connect in options["connect_calls"]:
            for call in module.calls(connect):
                target = call.args[0] if call.args else None
                if not is_temporary(target, temporary_names):
                    line = module.file.lines[call.lineno - 1]
                    yield Hit(module.file.path, call.lineno, line)
