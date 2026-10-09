from conftest import FIXTURE_NAMES, ProjectMaker, fixture_project

from honeywagon.capability import analyse, capability_map
from honeywagon.files import load_project
from honeywagon.models import BOUNDEDNESS, TOUCHES, CapabilityMap, NotChecked


def map_of(name: str) -> CapabilityMap:
    return capability_map(analyse(load_project(fixture_project(name))))


def tools(capabilities: CapabilityMap) -> dict[str, tuple[tuple[str, ...], str]]:
    return {
        capability.name: (capability.touches, capability.boundedness)
        for capability in capabilities.capabilities
        if capability.kind == "tool"
    }


def test_mcp_server_fixture_lists_what_each_tool_touches() -> None:
    assert tools(map_of("mcp-customer-db")) == {
        "run_query": (("database",), "free_form"),
        "export_customers": (("shell",), "free_form"),
        "fetch_invoice": (("network",), "free_form"),
        "add_note": (("database",), "parameterized"),
    }


def test_agent_fixture_lists_its_tools_and_its_settings() -> None:
    capabilities = map_of("agent-support-triage")

    assert tools(capabilities) == {
        "read_inbox": (("filesystem_read",), "fixed"),
        "lookup_customer": (("filesystem_read",), "parameterized"),
        "post_message": (("network",), "parameterized"),
    }
    (agent,) = capabilities.agents
    assert agent.permission_mode == "bypassPermissions"
    assert agent.has_turn_limit is False
    assert agent.declared_in.line == 49
    allowed = [c.name for c in capabilities.capabilities if c.kind == "allowed_tool"]
    assert allowed == [
        "mcp__support__read_inbox",
        "mcp__support__lookup_customer",
        "mcp__support__post_message",
    ]


def test_skill_fixture_lists_the_tools_allowed_without_asking() -> None:
    capabilities = map_of("skill-release-notes")

    allowed = {c.name: c for c in capabilities.capabilities}
    assert set(allowed) == {"Bash", "Read", "Grep"}
    assert allowed["Bash"].scope == "unrestricted"
    assert "shell" in allowed["Bash"].touches
    assert allowed["Bash"].requires_confirmation is False
    assert allowed["Bash"].declared_in.line == 4


def test_plugin_fixture_lists_its_mcp_server_and_its_hook() -> None:
    capabilities = map_of("plugin-team-helper")

    (server,) = capabilities.mcp_servers
    assert server.name == "issues"
    assert server.command == "npx -y @modelcontextprotocol/server-github"
    assert server.env == ("GITHUB_PERSONAL_ACCESS_TOKEN",)
    assert server.declared_in.line == 3
    (hook,) = capabilities.hooks
    assert hook.event == "SessionStart"
    assert hook.command.startswith("curl -fsSL")
    assert hook.declared_in.line == 8


def test_clean_fixture_has_restricted_tools_and_bounded_code() -> None:
    capabilities = map_of("clean-plugin")

    scopes = {
        c.name: c.scope for c in capabilities.capabilities if c.kind == "allowed_tool"
    }
    assert scopes == {
        "Read": "unrestricted",
        "Bash(git log *)": "restricted",
        "Bash(git describe *)": "restricted",
    }
    assert tools(capabilities) == {
        "add_note": (("database",), "parameterized"),
        "search_notes": (("database",), "parameterized"),
    }
    assert [hook.event for hook in capabilities.hooks] == ["PreToolUse"]
    assert [server.name for server in capabilities.mcp_servers] == ["notes"]


def test_every_value_in_the_maps_comes_from_the_closed_lists() -> None:
    for name in FIXTURE_NAMES:
        for capability in map_of(name).capabilities:
            assert set(capability.touches) <= set(TOUCHES)
            assert capability.boundedness in BOUNDEDNESS


def test_secret_in_a_command_is_redacted_in_the_map(make_project: ProjectMaker) -> None:
    key = "ghp_" + "FAKE-FIXTURE-NOT-A-REAL-TOKEN"
    config = (
        f'{{"mcpServers": {{"x": {{"command": "run", "args": ["--token", "{key}"]}}}}}}'
    )
    project = make_project({".mcp.json": config})

    (server,) = capability_map(analyse(project)).mcp_servers

    assert key not in server.command
    assert "REDACTED" in server.command


def test_permission_mode_of_a_settings_file_is_in_the_map(
    make_project: ProjectMaker,
) -> None:
    content = '{\n  "permissions": {\n    "defaultMode": "acceptEdits"\n  }\n}'
    project = make_project({".claude/settings.json": content})

    (setting,) = capability_map(analyse(project)).permission_modes

    assert setting.mode == "acceptEdits"
    assert (setting.declared_in.file, setting.declared_in.line) == (
        ".claude/settings.json",
        3,
    )


def test_files_that_cannot_be_parsed_are_reported(make_project: ProjectMaker) -> None:
    project = make_project(
        {
            "SKILL.md": "---\nallowed-tools: [Bash\n---\n# x\n",
            ".mcp.json": '{"mcpServers": ',
            "hooks/hooks.json": "not json",
        }
    )

    assert set(analyse(project).not_checked) == {
        NotChecked("SKILL.md", "invalid_frontmatter"),
        NotChecked(".mcp.json", "invalid_json"),
        NotChecked("hooks/hooks.json", "invalid_json"),
    }


def test_tool_that_passes_its_input_through_a_local_name_is_still_free_form(
    make_project: ProjectMaker,
) -> None:
    code = (
        "from claude_agent_sdk import tool\n\n\n"
        '@tool("run", "Run a query", {"sql": str})\n'
        "async def run(args):\n"
        '    statement = args["sql"]\n'
        "    return connection.execute(statement)\n"
    )
    project = make_project({"agent.py": code})

    assert tools(capability_map(analyse(project))) == {
        "run": (("database",), "free_form")
    }
