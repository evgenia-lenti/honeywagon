import pytest
from conftest import FIXTURE_NAMES, ProjectMaker, fixture_project

from honeywagon.capability import analyse, capability_map
from honeywagon.files import load_project
from honeywagon.models import (
    BOUNDEDNESS,
    DATA_ACTIONS,
    DATA_SCOPE_STATUSES,
    TOUCHES,
    Capability,
    CapabilityMap,
    DataScope,
    NotChecked,
    TableAccess,
)


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
        "find_customer": (("database",), "free_form"),
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
            assert capability.data_scope.status in DATA_SCOPE_STATUSES
            for access in capability.data_scope.tables:
                assert access.action in DATA_ACTIONS


def scopes(capabilities: CapabilityMap) -> dict[str, DataScope]:
    return {
        capability.name: capability.data_scope
        for capability in capabilities.capabilities
        if capability.kind == "tool"
    }


def tool_of(make_project: ProjectMaker, body: str, top: str = "") -> Capability:
    """Return the map entry of one MCP tool with this body."""
    lines = "\n".join(f"    {line}" for line in body.splitlines())
    code = (
        "import os\nimport sqlite3\n\nfrom mcp.server import MCPServer\n\n"
        f'mcp = MCPServer("x")\n{top}\n\n'
        f"@mcp.tool()\ndef do(value: str) -> str:\n{lines}\n"
    )
    project = make_project({"server.py": code})
    (capability,) = capability_map(analyse(project)).capabilities
    return capability


def scope_of(make_project: ProjectMaker, body: str, top: str = "") -> DataScope:
    return tool_of(make_project, body, top).data_scope


def test_mcp_server_fixture_lists_the_data_each_tool_reaches() -> None:
    assert scopes(map_of("mcp-customer-db")) == {
        "run_query": DataScope("any", database="customers.db"),
        "export_customers": DataScope("none"),
        "fetch_invoice": DataScope("none"),
        "add_note": DataScope(
            "known",
            database="customers.db",
            tables=(TableAccess("notes", "write", ("customer_id", "note")),),
        ),
        "find_customer": DataScope("any", database="customers.db"),
    }


def test_clean_fixture_lists_tables_and_columns_without_the_database() -> None:
    # The connection is opened in a helper function, which the reader does not follow.
    assert scopes(map_of("clean-plugin")) == {
        "add_note": DataScope(
            "known", tables=(TableAccess("notes", "write", ("body",)),)
        ),
        "search_notes": DataScope(
            "known", tables=(TableAccess("notes", "read", ("body", "id")),)
        ),
    }


def test_tool_that_is_not_code_has_an_unknown_data_scope() -> None:
    (bash, *_) = map_of("skill-release-notes").capabilities

    assert bash.data_scope == DataScope("unknown")


def test_statement_and_database_are_followed_through_constants(
    make_project: ProjectMaker,
) -> None:
    top = 'DB = "shop.db"\nQUERY = "SELECT name FROM customers WHERE id = ?"\n'
    body = (
        "conn = sqlite3.connect(DB)\nrows = conn.execute(QUERY, (value,))\nreturn rows"
    )

    assert scope_of(make_project, body, top) == DataScope(
        "known",
        database="shop.db",
        tables=(TableAccess("customers", "read", ("name", "id")),),
    )


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ('os.environ.get("SHOP_DB", "shop.db")', ("shop.db", "SHOP_DB")),
        ('os.getenv("SHOP_DB")', (None, "SHOP_DB")),
        ('os.environ["SHOP_DB"]', (None, "SHOP_DB")),
        ("find_database()", (None, None)),
    ],
    ids=["environment with default", "getenv", "environment item", "function"],
)
def test_database_read_from_the_environment_is_named_by_its_variable(
    make_project: ProjectMaker, target: str, expected: tuple[str | None, str | None]
) -> None:
    body = 'conn = sqlite3.connect(DB)\nconn.execute("DELETE FROM notes")\nreturn ""'

    scope = scope_of(make_project, body, f"DB = {target}\n")

    assert (scope.database, scope.database_variable) == expected
    assert scope.tables == (TableAccess("notes", "delete", ("*",)),)


def test_tool_that_opens_two_databases_names_neither(
    make_project: ProjectMaker,
) -> None:
    body = (
        'old = sqlite3.connect("old.db")\nnew = sqlite3.connect("new.db")\n'
        'new.execute("INSERT INTO notes (body) SELECT body FROM archive")\nreturn ""'
    )

    scope = scope_of(make_project, body)

    assert (scope.status, scope.database, scope.database_variable) == (
        "known",
        None,
        None,
    )


def test_sql_built_in_code_makes_the_scope_partial_or_unknown(
    make_project: ProjectMaker,
) -> None:
    built = 'conn.execute("SELECT * FROM " + TABLE)'
    constant = 'conn.execute("SELECT id FROM notes")'
    start = 'conn = sqlite3.connect("x.db")\n'

    partial = scope_of(make_project, f'{start}{constant}\n{built}\nreturn ""')
    unknown = scope_of(make_project, f'{start}{built}\nreturn ""')

    assert partial.status == "partial"
    assert partial.tables == (TableAccess("notes", "read", ("id",)),)
    assert (unknown.status, unknown.tables) == ("unknown", ())


def test_tool_that_only_opens_a_database_still_touches_one(
    make_project: ProjectMaker,
) -> None:
    project = make_project(
        {
            "server.py": (
                "import sqlite3\n\nfrom mcp.server import MCPServer\n\n"
                'mcp = MCPServer("x")\n\n\n'
                "@mcp.tool()\ndef do() -> str:\n"
                '    return save(sqlite3.connect("x.db"))\n'
            )
        }
    )

    (capability,) = capability_map(analyse(project)).capabilities

    assert capability.touches == ("database",)
    assert capability.data_scope == DataScope("unknown", database="x.db")


def test_tool_with_input_pasted_into_sql_is_free_form(
    make_project: ProjectMaker,
) -> None:
    body = (
        'conn = sqlite3.connect("x.db")\n'
        "conn.execute(f\"SELECT * FROM notes WHERE title = '{value}'\")\n"
        'return ""'
    )
    capability = tool_of(make_project, body)

    assert capability.data_scope.status == "any"
    assert capability.boundedness == "free_form"


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
