"""The data structures that pass through the whole audit chain."""

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

SCHEMA_VERSION = 1

SEVERITIES = ("critical", "error", "warning", "suggestion", "nitpick")
CONFIDENCES = ("high", "medium", "low")
FIX_EFFORTS = ("simple", "complex")
PROJECT_KINDS = ("plugin", "skill", "mcp_server", "agent")


@dataclass(frozen=True)
class Origin:
    layer: str
    source: str


@dataclass(frozen=True)
class Finding:
    id: str
    check_id: str
    title: str
    file: str
    line: int
    evidence: str
    consequence: str
    severity: str
    confidence: str
    fix_effort: str
    suggestion: str | None
    origin: Origin
    verification: str | None


@dataclass(frozen=True)
class NotChecked:
    """Something the audit did not look at, and the key of the reason why."""

    what: str
    reason: str


@dataclass(frozen=True)
class Verdict:
    key: str
    text: str
    partial: bool
    triggered_by: tuple[str, ...]


@dataclass(frozen=True)
class RunResult:
    schema_version: int
    tool_version: str
    project_kinds: tuple[str, ...]
    layers_ran: tuple[str, ...]
    checks_ran: tuple[str, ...]
    findings: tuple[Finding, ...]
    verdict: Verdict
    not_checked: tuple[NotChecked, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def finding_id(check_id: str, file: str, evidence: str) -> str:
    """Build the stable id of a finding.

    The id has no line number, so it stays the same when lines move. The
    evidence must already be redacted: a secret never goes into the hash.
    """
    normalised = " ".join(evidence.split())
    digest = hashlib.sha256(f"{file}\n{normalised}".encode()).hexdigest()
    return f"{check_id}:{digest[:6]}"
