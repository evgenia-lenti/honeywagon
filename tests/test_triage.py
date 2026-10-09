import json

from conftest import FIXTURE_NAMES, ProjectMaker, fixture_project

from honeywagon.capability import analyse, capability_map
from honeywagon.datafiles import load_data, load_texts
from honeywagon.files import Project, load_project
from honeywagon.models import RISK_TIERS, RiskGroup
from honeywagon.pipeline import run_audit
from honeywagon.triage import KINDS, risk_map


def groups_of(project: Project) -> dict[str, RiskGroup]:
    risks = risk_map(capability_map(analyse(project)))
    return {group.name: group for group in risks.groups}


def fixture_groups(name: str) -> dict[str, RiskGroup]:
    return groups_of(load_project(fixture_project(name)))


def reasons(group: RiskGroup) -> dict[str, tuple[str, ...]]:
    return {reason.key: reason.items for reason in group.reasons}


def test_mcp_server_fixture_puts_the_code_before_its_configuration() -> None:
    groups = fixture_groups("mcp-customer-db")

    assert [(g.name, g.kind, g.tier) for g in groups.values()] == [
        ("server.py", "code_tools", "high"),
        (".mcp.json", "mcp_servers", "medium"),
    ]
    assert reasons(groups["server.py"]) == {
        "free_form_input": (
            "run_query",
            "export_customers",
            "fetch_invoice",
            "find_customer",
        ),
        "runs_commands": ("export_customers",),
        "changes_data": ("add_note",),
        "data_not_limited": ("run_query", "find_customer"),
        "uses_network": ("fetch_invoice",),
    }


def test_agent_fixture_is_one_part_with_all_its_reasons() -> None:
    (group,) = fixture_groups("agent-support-triage").values()

    assert (group.name, group.kind, group.tier) == ("agent.py", "agent", "high")
    assert reasons(group) == {
        "no_permission_prompts": ("bypassPermissions",),
        "uses_network": ("post_message",),
        "reads_data": ("read_inbox", "lookup_customer"),
        "allowed_without_asking": (
            "mcp__support__read_inbox",
            "mcp__support__lookup_customer",
            "mcp__support__post_message",
        ),
        "runs_an_agent": (),
    }


def test_skill_that_allows_any_command_comes_first() -> None:
    (group,) = fixture_groups("skill-release-notes").values()

    assert (group.name, group.kind, group.tier) == ("SKILL.md", "skill", "high")
    assert reasons(group) == {
        "any_command_allowed": ("Bash",),
        "allowed_without_asking": ("Read", "Grep"),
    }


def test_plugin_fixture_puts_the_hook_before_the_rest() -> None:
    groups = fixture_groups("plugin-team-helper")

    assert [(g.name, g.kind, g.tier) for g in groups.values()] == [
        ("hooks/hooks.json", "hooks", "high"),
        (".mcp.json", "mcp_servers", "medium"),
        ("skills/standup/SKILL.md", "skill", "medium"),
    ]


def test_clean_fixture_has_parts_to_look_at_first_and_still_no_finding() -> None:
    result = run_audit(fixture_project("clean-plugin"))

    tiers = {group.name: group.tier for group in result.risk_map.groups}
    assert tiers == {
        "hooks/hooks.json": "high",
        "servers/notes_server.py": "high",
        ".mcp.json": "medium",
        "skills/changelog/SKILL.md": "medium",
    }
    assert result.findings == ()
    assert result.verdict.key == "no_reason_found"


def test_parts_are_ordered_by_tier_and_then_by_name() -> None:
    for name in FIXTURE_NAMES:
        groups = list(fixture_groups(name).values())

        assert groups == sorted(
            groups, key=lambda group: (RISK_TIERS.index(group.tier), group.name)
        )


def test_part_gets_the_highest_tier_among_its_reasons() -> None:
    for name in FIXTURE_NAMES:
        for group in fixture_groups(name).values():
            tiers = [reason.tier for reason in group.reasons]

            assert group.tier == min(tiers, key=RISK_TIERS.index)
            assert tiers == sorted(tiers, key=RISK_TIERS.index)


def test_every_reason_has_a_tier_and_a_text() -> None:
    tiers = load_data("risk.toml")["tiers"]
    texts = load_texts()

    assert set(tiers) == set(texts["risk_reasons"])
    assert set(tiers.values()) <= set(RISK_TIERS)
    assert set(texts["risk_tiers"]) == set(RISK_TIERS)
    assert set(texts["risk_kinds"]) == set(KINDS)


def test_tool_that_touches_nothing_is_looked_at_last(
    make_project: ProjectMaker,
) -> None:
    code = (
        "from mcp.server import MCPServer\n\n"
        'mcp = MCPServer("x")\n\n\n'
        "@mcp.tool()\ndef add(a: int, b: int) -> int:\n    return a + b\n"
    )

    (group,) = groups_of(make_project({"server.py": code})).values()

    assert (group.kind, group.tier) == ("code_tools", "low")
    assert reasons(group) == {"no_outside_effect": ("add",)}


def test_tool_with_sql_that_could_not_be_read_comes_first(
    make_project: ProjectMaker,
) -> None:
    code = (
        "import sqlite3\n\nfrom mcp.server import MCPServer\n\n"
        'mcp = MCPServer("x")\n\n\n'
        "@mcp.tool()\ndef report() -> list:\n"
        '    return sqlite3.connect("x.db").execute(build_query()).fetchall()\n'
    )

    (group,) = groups_of(make_project({"server.py": code})).values()

    assert group.tier == "high"
    assert reasons(group) == {"data_access_unknown": ("report",)}


def settings(mode: str, with_hook: bool = False) -> dict[str, str]:
    content: dict[str, object] = {"permissions": {"defaultMode": mode}}
    if with_hook:
        hook = {"type": "command", "command": "echo done"}
        content["hooks"] = {"Stop": [{"hooks": [hook]}]}
    return {
        "SKILL.md": "---\nname: x\n---\n\n# x\n",
        ".claude/settings.json": json.dumps(content, indent=2),
    }


def test_settings_file_that_switches_questions_off_comes_first(
    make_project: ProjectMaker,
) -> None:
    (group,) = groups_of(make_project(settings("bypassPermissions"))).values()

    assert (group.kind, group.tier) == ("settings", "high")
    assert reasons(group) == {"no_permission_prompts": ("bypassPermissions",)}


def test_settings_file_with_another_mode_comes_next(
    make_project: ProjectMaker,
) -> None:
    (group,) = groups_of(make_project(settings("acceptEdits"))).values()

    assert (group.kind, group.tier) == ("settings", "medium")
    assert reasons(group) == {"sets_permission_mode": ("acceptEdits",)}


def test_file_with_a_mode_and_a_hook_is_one_settings_part(
    make_project: ProjectMaker,
) -> None:
    project = make_project(settings("acceptEdits", with_hook=True))

    (group,) = groups_of(project).values()

    assert (group.kind, group.tier) == ("settings", "high")
    assert reasons(group) == {
        "runs_by_itself": ("Stop",),
        "sets_permission_mode": ("acceptEdits",),
    }
