"""The chain of steps of one audit: read, detect, map, check, classify."""

from collections import Counter
from importlib.metadata import version
from pathlib import Path

from honeywagon.capability import Analysis, analyse, capability_map
from honeywagon.checks import Check, Hit, load_checks
from honeywagon.classify import confidence_of, propose_verdict
from honeywagon.datafiles import load_texts
from honeywagon.deps.manifests import Dependency
from honeywagon.deps.osv import Lookup
from honeywagon.detect import detect
from honeywagon.files import load_project
from honeywagon.guard.redact import safe_evidence
from honeywagon.models import (
    SCHEMA_VERSION,
    SEVERITIES,
    CapabilityMap,
    Finding,
    NotChecked,
    Origin,
    RiskMap,
    RunResult,
    Verdict,
    finding_id,
)
from honeywagon.triage import risk_map

LAYER = "deterministic"
# What this layer never covers, or does not cover yet. Always reported.
NOT_COVERED = (
    "dangerous_combination",
    "model_checkers",
    "dynamic_tester",
)
# Reported only when the project has tools written in code.
NOT_COVERED_IN_CODE = ("called_functions",)
# Data scopes that leave SQL of a tool unread.
SQL_NOT_READ = ("partial", "unknown")


def _finding(check: Check, hit: Hit, seen: Counter[str]) -> Finding:
    text = load_texts()["checks"][check.check_id]
    evidence = safe_evidence(hit.evidence)
    identifier = finding_id(check.check_id, hit.file, evidence)
    seen[identifier] += 1
    if seen[identifier] > 1:
        identifier = f"{identifier}-{seen[identifier]}"
    origin = Origin(layer=LAYER, source=check.source)
    values = {key: safe_evidence(value) for key, value in (hit.values or {}).items()}
    return Finding(
        id=identifier,
        check_id=check.check_id,
        title=text["title"],
        file=hit.file,
        line=hit.line,
        evidence=evidence,
        consequence=text["consequence"].format(**values),
        severity=hit.severity or check.severity,
        confidence=confidence_of(origin, None),
        fix_effort=check.fix_effort,
        suggestion=safe_evidence(hit.suggestion) if hit.suggestion else None,
        origin=origin,
        verification=None,
    )


def _not_covered(key: str) -> NotChecked:
    return NotChecked(load_texts()["not_checked_items"][key], key)


def _dependencies_not_checked(analysis: Analysis) -> list[NotChecked]:
    """Say which dependencies were not looked up, and why."""
    if not analysis.dependencies:
        return []
    pinned = [d for d in analysis.dependencies if d.version]
    not_checked = []

    def entry(dependencies: list[Dependency], reason: str) -> None:
        labels = dict.fromkeys(safe_evidence(d.label) for d in dependencies)
        if labels:
            not_checked.append(NotChecked(", ".join(labels), reason))

    entry([d for d in analysis.dependencies if not d.version], "dependency_not_pinned")
    if not analysis.looked_up:
        entry(pinned, "dependency_lookup_off")
    else:
        failed = [d for d in pinned if analysis.advisories.get(d.package) is None]
        entry(failed, "dependency_lookup_failed")
    not_checked.append(_not_covered("indirect_dependencies"))
    return not_checked


def run_audit(root: Path, lookup: Lookup | None = None) -> RunResult:
    """Audit one project folder with the deterministic layer.

    The lookup asks a public database about known security problems of the
    dependencies. Without it the audit sends nothing anywhere.
    """
    texts = load_texts()
    project = load_project(root)
    kinds, not_parsed = detect(project)
    not_checked = [*project.not_read, *not_parsed]
    findings: list[Finding] = []
    checks_ran: list[str] = []
    capabilities = CapabilityMap()
    risks = RiskMap()
    looked_up: tuple[str, ...] = ()
    verdict_key = "nothing_to_audit"
    triggered_by: tuple[str, ...] = ()

    if not kinds:
        not_checked.insert(0, _not_covered("no_agentic_artifact"))
    else:
        analysis = analyse(project, lookup)
        looked_up = tuple(
            safe_evidence(" ".join(package)) for package in analysis.advisories
        )
        capabilities = capability_map(analysis)
        risks = risk_map(capabilities)
        not_checked.extend(analysis.not_checked)
        seen: Counter[str] = Counter()
        for check in load_checks():
            if not check.kinds.intersection(kinds):
                continue
            checks_ran.append(check.check_id)
            for hit in check.function(analysis, check.options):
                findings.append(_finding(check, hit, seen))
        findings.sort(
            key=lambda f: (SEVERITIES.index(f.severity), f.file, f.line, f.check_id)
        )
        verdict_key, triggered_by = propose_verdict(findings)
        if analysis.tools:
            not_checked.extend(_not_covered(key) for key in NOT_COVERED_IN_CODE)
        sql_not_read = [
            capability.name
            for capability in capabilities.capabilities
            if capability.kind == "tool"
            and capability.data_scope.status in SQL_NOT_READ
        ]
        if sql_not_read:
            not_checked.append(NotChecked(", ".join(sql_not_read), "sql_not_read"))
        not_checked.extend(_dependencies_not_checked(analysis))
        remote = [server.name for server in capabilities.mcp_servers if server.remote]
        if remote:
            what = safe_evidence(", ".join(remote))
            not_checked.append(NotChecked(what, "remote_server_authentication"))
        not_checked.extend(_not_covered(key) for key in NOT_COVERED)

    return RunResult(
        schema_version=SCHEMA_VERSION,
        tool_version=version("honeywagon"),
        project_kinds=kinds,
        layers_ran=(LAYER,) if kinds else (),
        checks_ran=tuple(checks_ran),
        looked_up=looked_up,
        capability_map=capabilities,
        risk_map=risks,
        findings=tuple(findings),
        verdict=Verdict(
            key=verdict_key,
            text=texts["verdict"][verdict_key],
            partial=bool(kinds),
            triggered_by=triggered_by,
        ),
        not_checked=tuple(not_checked),
    )
