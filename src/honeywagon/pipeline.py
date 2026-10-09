"""The chain of steps of one audit: read, detect, check, classify."""

from collections import Counter
from importlib.metadata import version
from pathlib import Path

from honeywagon.checks import Check, Hit, load_checks
from honeywagon.classify import confidence_of, propose_verdict
from honeywagon.datafiles import load_texts
from honeywagon.detect import detect
from honeywagon.files import load_project
from honeywagon.guard.redact import safe_evidence
from honeywagon.models import (
    SCHEMA_VERSION,
    SEVERITIES,
    Finding,
    NotChecked,
    Origin,
    RunResult,
    Verdict,
    finding_id,
)

LAYER = "deterministic"
# What this layer never covers, or does not cover yet. Always reported.
NOT_COVERED = (
    "other_deterministic_checks",
    "external_scanner",
    "dependency_vulnerabilities",
    "model_checkers",
    "dynamic_tester",
)


def _finding(check: Check, hit: Hit, seen: Counter[str]) -> Finding:
    text = load_texts()["checks"][check.check_id]
    evidence = safe_evidence(hit.evidence)
    identifier = finding_id(check.check_id, hit.file, evidence)
    seen[identifier] += 1
    if seen[identifier] > 1:
        identifier = f"{identifier}-{seen[identifier]}"
    origin = Origin(layer=LAYER, source=check.source)
    return Finding(
        id=identifier,
        check_id=check.check_id,
        title=text["title"],
        file=hit.file,
        line=hit.line,
        evidence=evidence,
        consequence=text["consequence"],
        severity=check.severity,
        confidence=confidence_of(origin, None),
        fix_effort=check.fix_effort,
        suggestion=None,
        origin=origin,
        verification=None,
    )


def _not_covered(key: str) -> NotChecked:
    return NotChecked(load_texts()["not_checked_items"][key], key)


def run_audit(root: Path) -> RunResult:
    """Audit one project folder with the deterministic layer."""
    texts = load_texts()
    project = load_project(root)
    kinds, not_parsed = detect(project)
    not_checked = [*project.not_read, *not_parsed]
    findings: list[Finding] = []
    checks_ran: list[str] = []

    verdict_key = "nothing_to_audit"
    triggered_by: tuple[str, ...] = ()

    if not kinds:
        not_checked.insert(0, _not_covered("no_agentic_artifact"))
    else:
        seen: Counter[str] = Counter()
        for check in load_checks():
            if not check.kinds.intersection(kinds):
                continue
            checks_ran.append(check.check_id)
            for result in check.function(project, check.options):
                if isinstance(result, Hit):
                    findings.append(_finding(check, result, seen))
                else:
                    not_checked.append(result)
        findings.sort(
            key=lambda f: (SEVERITIES.index(f.severity), f.file, f.line, f.check_id)
        )
        verdict_key, triggered_by = propose_verdict(findings)
        not_checked.extend(_not_covered(key) for key in NOT_COVERED)

    return RunResult(
        schema_version=SCHEMA_VERSION,
        tool_version=version("honeywagon"),
        project_kinds=kinds,
        layers_ran=(LAYER,) if kinds else (),
        checks_ran=tuple(checks_ran),
        findings=tuple(findings),
        verdict=Verdict(
            key=verdict_key,
            text=texts["verdict"][verdict_key],
            partial=bool(kinds),
            triggered_by=triggered_by,
        ),
        not_checked=tuple(not_checked),
    )
