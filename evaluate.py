"""Compare the audit tool's findings with the planted mistakes in fixtures/.

Usage:
    python evaluate.py
    python evaluate.py --results <folder> [--layer deterministic|model]

<folder> holds one <fixture>.json per fixture: a JSON list of findings, or an
object with a "findings" list. Each finding needs "check_id", "file" and "line".
Without --results no fixture has findings, so every planted mistake is missed.
"""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
LINE_TOLERANCE = 3
LAYERS = ("deterministic", "model")


@dataclass(frozen=True)
class Expected:
    check_id: str
    file: str
    line: int
    severity: str
    layer: str
    contains: str


@dataclass(frozen=True)
class Finding:
    check_id: str
    file: str
    line: int


@dataclass(frozen=True)
class Fixture:
    name: str
    project_kind: str
    project_dir: Path
    expected: tuple[Expected, ...]


@dataclass(frozen=True)
class FixtureResult:
    fixture: Fixture
    found: tuple[Expected, ...]
    missed: tuple[Expected, ...]
    false: tuple[Finding, ...]


@dataclass
class Counts:
    found: int = 0
    false: int = 0
    missed: int = 0

    @property
    def planted(self) -> int:
        return self.found + self.missed


def normalise_path(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def load_fixtures(fixtures_dir: Path) -> list[Fixture]:
    fixtures = []
    for expected_file in sorted(fixtures_dir.glob("*/expected.json")):
        data = json.loads(expected_file.read_text(encoding="utf-8"))
        fixtures.append(
            Fixture(
                name=expected_file.parent.name,
                project_kind=data["project_kind"],
                project_dir=expected_file.parent / "project",
                expected=tuple(Expected(**entry) for entry in data["expected"]),
            )
        )
    return fixtures


def load_findings(results_file: Path) -> list[Finding]:
    data: Any = json.loads(results_file.read_text(encoding="utf-8"))
    entries = data["findings"] if isinstance(data, dict) else data
    return [
        Finding(entry["check_id"], normalise_path(entry["file"]), int(entry["line"]))
        for entry in entries
    ]


def evaluate_fixture(
    fixture: Fixture, findings: Sequence[Finding], layer: str | None = None
) -> FixtureResult:
    """Match each finding to at most one planted mistake.

    A finding matches a planted mistake with the same check and file whose line
    is within LINE_TOLERANCE. With a layer, only that layer's mistakes are
    counted, and a finding that matches a mistake of the other layer is ignored.
    """
    unmatched = list(fixture.expected)
    found = []
    false = []
    for finding in findings:
        candidates = [
            expected
            for expected in unmatched
            if expected.check_id == finding.check_id
            and expected.file == finding.file
            and abs(expected.line - finding.line) <= LINE_TOLERANCE
        ]
        if not candidates:
            false.append(finding)
            continue
        closest = min(
            candidates, key=lambda expected: abs(expected.line - finding.line)
        )
        unmatched.remove(closest)
        found.append(closest)
    return FixtureResult(
        fixture=fixture,
        found=tuple(e for e in found if layer in (None, e.layer)),
        missed=tuple(e for e in unmatched if layer in (None, e.layer)),
        false=tuple(false),
    )


def count_per_check(results: Sequence[FixtureResult]) -> dict[str, Counts]:
    counts: dict[str, Counts] = {}
    for result in results:
        for expected in result.found:
            counts.setdefault(expected.check_id, Counts()).found += 1
        for expected in result.missed:
            counts.setdefault(expected.check_id, Counts()).missed += 1
        for finding in result.false:
            counts.setdefault(finding.check_id, Counts()).false += 1
    return counts


def count_per_kind(results: Sequence[FixtureResult]) -> dict[str, Counts]:
    counts: dict[str, Counts] = {}
    for result in results:
        kind = counts.setdefault(result.fixture.project_kind, Counts())
        kind.found += len(result.found)
        kind.missed += len(result.missed)
        kind.false += len(result.false)
    return counts


def count_per_fixture(results: Sequence[FixtureResult]) -> dict[str, Counts]:
    return {
        result.fixture.name: Counts(
            found=len(result.found), false=len(result.false), missed=len(result.missed)
        )
        for result in results
    }


def format_table(label: str, rows: dict[str, Counts]) -> list[str]:
    width = max(len(label), *(len(name) for name in rows))
    lines = [f"{label:<{width}}  planted  found  false  missed"]
    for name in sorted(rows):
        row = rows[name]
        counts = f"{row.planted:>7}  {row.found:>5}  {row.false:>5}  {row.missed:>6}"
        lines.append(f"{name:<{width}}  {counts}")
    return lines


def format_report(
    results: Sequence[FixtureResult],
    layer: str | None,
    results_dir: Path | None,
    fixtures_without_results: Sequence[str],
) -> str:
    lines = [f"Fixtures: {len(results)}    Layer: {layer or 'all'}"]
    if results_dir is None:
        lines.append("No tool output given: every planted mistake counts as missed.")
    else:
        lines.append(f"Tool output: {results_dir}")
    if fixtures_without_results:
        lines.append("No results file for: " + ", ".join(fixtures_without_results))
    lines += ["", *format_table("check_id", count_per_check(results))]
    lines += ["", *format_table("project kind", count_per_kind(results))]
    lines += ["", *format_table("fixture", count_per_fixture(results))]

    lines += ["", "Missed"]
    missed = [
        f"  {result.fixture.name}  {expected.check_id}  {expected.file}:{expected.line}"
        for result in results
        for expected in result.missed
    ]
    lines += missed or ["  (none)"]

    lines += ["", "False findings"]
    false = [
        f"  {result.fixture.name}  {finding.check_id}  {finding.file}:{finding.line}"
        for result in results
        for finding in result.false
    ]
    lines += false or ["  (none)"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare the tool's findings with the planted mistakes."
    )
    parser.add_argument(
        "--results",
        type=Path,
        help="folder with one <fixture>.json of findings per fixture",
    )
    parser.add_argument(
        "--layer", choices=LAYERS, help="count only the planted mistakes of this layer"
    )
    args = parser.parse_args(argv)
    if args.results is not None and not args.results.is_dir():
        parser.error(f"not a folder: {args.results}")

    results = []
    fixtures_without_results = []
    for fixture in load_fixtures(FIXTURES_DIR):
        findings: list[Finding] = []
        if args.results is not None:
            results_file = args.results / f"{fixture.name}.json"
            if results_file.is_file():
                findings = load_findings(results_file)
            else:
                fixtures_without_results.append(fixture.name)
        results.append(evaluate_fixture(fixture, findings, args.layer))

    print(format_report(results, args.layer, args.results, fixtures_without_results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
