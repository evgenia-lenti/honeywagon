"""The data structures that pass through the whole audit chain."""

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

SCHEMA_VERSION = 2

SEVERITIES = ("critical", "error", "warning", "suggestion", "nitpick")
CONFIDENCES = ("high", "medium", "low")
FIX_EFFORTS = ("simple", "complex")
PROJECT_KINDS = ("plugin", "skill", "mcp_server", "agent")
TOUCHES = (
    "filesystem_read",
    "filesystem_write",
    "shell",
    "network",
    "database",
    "secrets",
    "external_content",
)
BOUNDEDNESS = ("fixed", "parameterized", "free_form", "unknown")
DATA_ACTIONS = ("read", "write", "delete", "schema")
DATA_SCOPE_STATUSES = ("none", "known", "partial", "any", "unknown")
RISK_TIERS = ("high", "medium", "low")
# In the columns of a TableAccess: every column of the table.
ALL_COLUMNS = "*"


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
class Location:
    file: str
    line: int


@dataclass(frozen=True)
class TableAccess:
    """One table and one thing done to it. No columns means they are not known,
    or that the action is on the table as a whole."""

    table: str
    action: str
    columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class DataScope:
    """Which data a tool reaches, as far as its SQL could be read.

    `none`: no database. `known`: every statement was read. `partial`: some
    were. `any`: a statement, or a piece of one, comes from the input, so the
    code sets no limit. `unknown`: nothing could be read.
    """

    status: str
    database: str | None = None
    database_variable: str | None = None
    tables: tuple[TableAccess, ...] = ()


@dataclass(frozen=True)
class Capability:
    """One thing Claude may use: a tool allowed without asking, or a tool in code."""

    name: str
    kind: str
    declared_in: Location
    scope: str
    touches: tuple[str, ...]
    boundedness: str
    data_scope: DataScope
    requires_confirmation: bool | None


@dataclass(frozen=True)
class McpServerInfo:
    name: str
    declared_in: Location
    command: str
    env: tuple[str, ...]


@dataclass(frozen=True)
class HookInfo:
    event: str
    command: str
    declared_in: Location


@dataclass(frozen=True)
class AgentInfo:
    declared_in: Location
    permission_mode: str | None
    has_turn_limit: bool | None


@dataclass(frozen=True)
class PermissionModeInfo:
    """The permission mode that a settings file makes sessions start in."""

    declared_in: Location
    mode: str


@dataclass(frozen=True)
class CapabilityMap:
    """What the project can do. It lists facts and judges nothing."""

    capabilities: tuple[Capability, ...] = ()
    mcp_servers: tuple[McpServerInfo, ...] = ()
    hooks: tuple[HookInfo, ...] = ()
    agents: tuple[AgentInfo, ...] = ()
    permission_modes: tuple[PermissionModeInfo, ...] = ()


@dataclass(frozen=True)
class RiskReason:
    """Why a part deserves attention, and the tools or hooks that cause it."""

    key: str
    tier: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class RiskGroup:
    """One part of the project that gives capabilities, named by its file."""

    name: str
    kind: str
    tier: str
    reasons: tuple[RiskReason, ...]


@dataclass(frozen=True)
class RiskMap:
    """Where to look first. A guide for attention: it holds no finding."""

    groups: tuple[RiskGroup, ...] = ()


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
    capability_map: CapabilityMap
    risk_map: RiskMap
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
