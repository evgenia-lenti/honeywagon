"""The registry that joins each check's definition (data) with its function."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.datafiles import load_data


@dataclass(frozen=True)
class Hit:
    """One place where a check found its mistake.

    The suggestion is the line as it should become. A check sets it only when
    it knows the exact text.
    """

    file: str
    line: int
    evidence: str
    suggestion: str | None = None


CheckFunction = Callable[[Analysis, Mapping[str, Any]], Iterable[Hit]]
DEFINITION_KEYS = frozenset({"severity", "fix_effort", "kinds"})


@dataclass(frozen=True)
class Check:
    check_id: str
    severity: str
    fix_effort: str
    kinds: frozenset[str]
    options: Mapping[str, Any]
    function: CheckFunction

    @property
    def source(self) -> str:
        return self.function.__module__.removeprefix("honeywagon.")


_functions: dict[str, CheckFunction] = {}


def register(check_id: str) -> Callable[[CheckFunction], CheckFunction]:
    """Mark a function as the code of the check with this id."""

    def decorator(function: CheckFunction) -> CheckFunction:
        _functions[check_id] = function
        return function

    return decorator


def load_checks() -> tuple[Check, ...]:
    """Return every check that has both a definition and a function."""
    definitions = load_data("checks.toml")
    return tuple(
        Check(
            check_id=check_id,
            severity=definition["severity"],
            fix_effort=definition["fix_effort"],
            kinds=frozenset(definition["kinds"]),
            options={k: v for k, v in definition.items() if k not in DEFINITION_KEYS},
            function=_functions[check_id],
        )
        for check_id, definition in definitions.items()
    )
