"""Read what the configuration files declare: allowed tools, MCP servers, hooks."""

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from honeywagon.files import Project, ProjectFile
from honeywagon.frontmatter import FrontmatterError, frontmatter_values
from honeywagon.models import NotChecked

SKILL_FILE = "SKILL.md"
MCP_CONFIG_FILE = ".mcp.json"
SETTINGS_FILES = ("settings.json", "settings.local.json")
HOOK_FILES = ("hooks.json", *SETTINGS_FILES)

# One tool name, with its optional rule in parentheses: Read, Bash(git log *).
TOOL = re.compile(r"[^\s,()]+(?:\([^)]*\))?")


@dataclass(frozen=True)
class AllowedTool:
    """A tool that Claude may use without asking."""

    name: str
    file: str
    line: int

    @property
    def base_name(self) -> str:
        return self.name.partition("(")[0]

    @property
    def is_restricted(self) -> bool:
        rule = self.name.partition("(")[2].rstrip(")").strip()
        return bool(rule) and rule != "*"


@dataclass(frozen=True)
class McpServer:
    name: str
    file: str
    line: int
    command: str | None
    args: tuple[str, ...]
    env: tuple[str, ...]
    url: str | None
    # The headers sent to a remote server, as (name, value). The values are raw
    # text from the project: they never go into an output as they are.
    headers: tuple[tuple[str, str], ...] = ()

    @property
    def is_remote(self) -> bool:
        return self.url is not None


@dataclass(frozen=True)
class Hook:
    event: str
    command: str
    file: str
    line: int


@dataclass(frozen=True)
class PermissionMode:
    """The permission mode that a settings file makes sessions start in."""

    mode: str
    file: str
    line: int


def _load_json(file: ProjectFile) -> Any:
    try:
        return json.loads(file.text)
    except json.JSONDecodeError:
        return NotChecked(file.path, "invalid_json")


def read_allowed_tools(project: Project) -> Iterator[AllowedTool | NotChecked]:
    for file in project.named(SKILL_FILE):
        try:
            values = frontmatter_values(file, "allowed-tools")
        except FrontmatterError:
            yield NotChecked(file.path, "invalid_frontmatter")
            continue
        for value in values:
            for name in TOOL.findall(value.text):
                yield AllowedTool(name, file.path, value.line)


def read_mcp_servers(project: Project) -> Iterator[McpServer | NotChecked]:
    for file in project.named(MCP_CONFIG_FILE):
        data = _load_json(file)
        if isinstance(data, NotChecked):
            yield data
            continue
        servers = data.get("mcpServers") if isinstance(data, dict) else None
        if not isinstance(servers, dict):
            continue
        last_line = 0
        for name, server in servers.items():
            if not isinstance(server, dict):
                continue
            line = file.find_line(f"{json.dumps(name)}:", last_line) or 1
            last_line = line
            command = server.get("command")
            args = server.get("args")
            env = server.get("env")
            url = server.get("url")
            headers = server.get("headers")
            yield McpServer(
                name=name,
                file=file.path,
                line=line,
                command=command if isinstance(command, str) else None,
                args=tuple(str(a) for a in args) if isinstance(args, list) else (),
                env=tuple(env) if isinstance(env, dict) else (),
                url=url if isinstance(url, str) else None,
                headers=tuple(
                    (str(key), value)
                    for key, value in (
                        headers if isinstance(headers, dict) else {}
                    ).items()
                    if isinstance(value, str)
                ),
            )


def read_permission_modes(project: Project) -> Iterator[PermissionMode]:
    """Yield the `defaultMode` of every settings file that sets one.

    A settings file that is not valid JSON is reported by `read_hooks`.
    """
    for file in project.named(*SETTINGS_FILES):
        data = _load_json(file)
        if not isinstance(data, dict):
            continue
        permissions = data.get("permissions")
        mode = permissions.get("defaultMode") if isinstance(permissions, dict) else None
        if isinstance(mode, str):
            line = file.find_line('"defaultMode"') or 1
            yield PermissionMode(mode, file.path, line)


def _hook_commands(value: Any) -> Iterator[str]:
    """Yield the command of every command hook, wherever it sits in the JSON."""
    if isinstance(value, dict):
        command = value.get("command")
        if value.get("type") == "command" and isinstance(command, str):
            yield command
        for child in value.values():
            yield from _hook_commands(child)
    elif isinstance(value, list):
        for child in value:
            yield from _hook_commands(child)


def read_hooks(project: Project) -> Iterator[Hook | NotChecked]:
    for file in project.named(*HOOK_FILES):
        data = _load_json(file)
        if isinstance(data, NotChecked):
            yield data
            continue
        events = data.get("hooks") if isinstance(data, dict) else None
        if not isinstance(events, dict):
            continue
        last_line = 0
        for event, matchers in events.items():
            for command in _hook_commands(matchers):
                line = file.find_line(json.dumps(command), last_line) or 1
                last_line = line
                yield Hook(event, command, file.path, line)
