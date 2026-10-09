"""Work out what a project can do, once per audit, before the checks run."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import cached_property
from typing import TypeVar

from honeywagon.capability.config_files import (
    AllowedTool,
    Hook,
    McpServer,
    PermissionMode,
    read_allowed_tools,
    read_hooks,
    read_mcp_servers,
    read_permission_modes,
)
from honeywagon.capability.data_scope import data_scope
from honeywagon.capability.python_code import (
    AgentOptions,
    PythonModule,
    PythonTool,
    parse_python,
)
from honeywagon.datafiles import load_data
from honeywagon.deps.manifests import Dependency, read_dependencies
from honeywagon.deps.osv import Advisory, Lookup, Package, look_up_all
from honeywagon.files import Project
from honeywagon.guard.redact import safe_evidence
from honeywagon.models import (
    AgentInfo,
    Capability,
    CapabilityMap,
    DataScope,
    HookInfo,
    Location,
    McpServerInfo,
    NotChecked,
    PermissionModeInfo,
)

T = TypeVar("T")


@dataclass(frozen=True)
class Analysis:
    """Everything the checks may look at. It holds raw text from the project,
    so it never leaves the program: the capability map is its safe summary."""

    project: Project
    allowed_tools: tuple[AllowedTool, ...]
    mcp_servers: tuple[McpServer, ...]
    hooks: tuple[Hook, ...]
    permission_modes: tuple[PermissionMode, ...]
    python: tuple[PythonModule, ...]
    not_checked: tuple[NotChecked, ...]
    dependencies: tuple[Dependency, ...] = ()
    # What the lookup said about each dependency with an exact version. Empty
    # when no lookup was asked for. None for a package whose lookup failed.
    advisories: Mapping[Package, tuple[Advisory, ...] | None] = field(
        default_factory=dict
    )
    looked_up: bool = False

    @cached_property
    def tools(self) -> tuple[PythonTool, ...]:
        return tuple(tool for module in self.python for tool in module.tools)

    @cached_property
    def agent_options(self) -> tuple[AgentOptions, ...]:
        return tuple(o for module in self.python for o in module.agent_options)


def _keep(
    items: Iterable[T | NotChecked], not_checked: list[NotChecked]
) -> tuple[T, ...]:
    """Return the items that were read, and collect the files that were not."""
    kept = []
    for item in items:
        if isinstance(item, NotChecked):
            not_checked.append(item)
        else:
            kept.append(item)
    return tuple(kept)


def analyse(project: Project, lookup: Lookup | None = None) -> Analysis:
    """Read the configuration files and the Python code of the project.

    The lookup asks about known security problems of dependencies. Without it
    nothing leaves the computer.
    """
    not_checked: list[NotChecked] = []
    allowed_tools = _keep(read_allowed_tools(project), not_checked)
    mcp_servers = _keep(read_mcp_servers(project), not_checked)
    hooks = _keep(read_hooks(project), not_checked)
    # A file that cannot be parsed is already reported by the detection step.
    modules = (parse_python(file) for file in project.with_suffix(".py"))
    python = tuple(module for module in modules if module is not None)
    dependencies = _keep(read_dependencies(project, mcp_servers), not_checked)
    pinned = [dependency.package for dependency in dependencies if dependency.version]
    return Analysis(
        project=project,
        allowed_tools=allowed_tools,
        mcp_servers=mcp_servers,
        hooks=hooks,
        permission_modes=tuple(read_permission_modes(project)),
        python=python,
        not_checked=tuple(not_checked),
        dependencies=dependencies,
        advisories=look_up_all(pinned, lookup) if lookup else {},
        looked_up=lookup is not None,
    )


def _allowed_tool(tool: AllowedTool) -> Capability:
    touches = load_data("builtin_tools.toml")["touches"].get(tool.base_name, [])
    return Capability(
        name=tool.name,
        kind="allowed_tool",
        declared_in=Location(tool.file, tool.line),
        scope="restricted" if tool.is_restricted else "unrestricted",
        touches=tuple(touches),
        boundedness="unknown",
        data_scope=DataScope("unknown"),
        requires_confirmation=False,
    )


def _code_tool(tool: PythonTool) -> Capability:
    return Capability(
        name=tool.name,
        kind="tool",
        declared_in=Location(tool.file, tool.line),
        scope="unrestricted" if tool.boundedness == "free_form" else "restricted",
        touches=tool.touches,
        boundedness=tool.boundedness,
        data_scope=data_scope(tool),
        requires_confirmation=None,
    )


def _agent(options: AgentOptions) -> AgentInfo:
    mode = options.keywords.get("permission_mode")
    has_limit: bool | None = "max_turns" in options.keywords
    if not has_limit and options.has_unpacked_keywords:
        has_limit = None
    return AgentInfo(
        declared_in=Location(options.file, options.line),
        permission_mode=str(mode.value) if mode and mode.value is not None else None,
        has_turn_limit=has_limit,
    )


def capability_map(analysis: Analysis) -> CapabilityMap:
    """Summarise the analysis as facts that are safe to show: no secret in it."""
    agent_tools = [
        AllowedTool(name, options.file, line)
        for options in analysis.agent_options
        for name, line in options.allowed_tools
    ]
    return CapabilityMap(
        capabilities=(
            *(_allowed_tool(tool) for tool in (*analysis.allowed_tools, *agent_tools)),
            *(_code_tool(tool) for tool in analysis.tools),
        ),
        mcp_servers=tuple(
            McpServerInfo(
                name=server.name,
                declared_in=Location(server.file, server.line),
                command=safe_evidence(
                    " ".join([server.command or server.url or "", *server.args])
                ),
                env=server.env,
            )
            for server in analysis.mcp_servers
        ),
        hooks=tuple(
            HookInfo(
                event=hook.event,
                command=safe_evidence(hook.command),
                declared_in=Location(hook.file, hook.line),
            )
            for hook in analysis.hooks
        ),
        agents=tuple(_agent(options) for options in analysis.agent_options),
        permission_modes=tuple(
            PermissionModeInfo(Location(setting.file, setting.line), setting.mode)
            for setting in analysis.permission_modes
        ),
    )
