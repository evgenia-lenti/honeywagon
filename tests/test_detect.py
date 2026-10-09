import pytest
from conftest import ProjectMaker, fixture_project

from honeywagon.detect import detect
from honeywagon.files import load_project
from honeywagon.models import NotChecked


@pytest.mark.parametrize(
    ("name", "kinds"),
    [
        ("skill-release-notes", ("skill",)),
        ("plugin-team-helper", ("plugin",)),
        ("mcp-customer-db", ("mcp_server",)),
        ("agent-support-triage", ("agent",)),
        ("clean-plugin", ("mcp_server", "plugin")),
    ],
)
def test_kinds_of_the_fixtures(name: str, kinds: tuple[str, ...]) -> None:
    found, not_parsed = detect(load_project(fixture_project(name)))

    assert found == kinds
    assert not_parsed == ()


def test_project_without_agentic_files_has_no_kind(make_project: ProjectMaker) -> None:
    project = make_project({"README.md": "# A website", "app.py": "import flask"})

    assert detect(project) == ((), ())


def test_skill_inside_a_plugin_counts_as_the_plugin(make_project: ProjectMaker) -> None:
    project = make_project(
        {".claude-plugin/plugin.json": "{}", "skills/x/SKILL.md": "# x"}
    )

    assert detect(project)[0] == ("plugin",)


def test_python_file_that_cannot_be_parsed_is_reported(
    make_project: ProjectMaker,
) -> None:
    project = make_project({"SKILL.md": "# x", "broken.py": "def (:"})

    assert detect(project) == (("skill",), (NotChecked("broken.py", "invalid_python"),))
