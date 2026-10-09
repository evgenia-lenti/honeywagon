"""Dependencies: reading them, looking them up, and the dep-security check."""

import io
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import ProjectMaker, fixture_project

import evaluate
from honeywagon.capability import analyse
from honeywagon.checks import Hit, load_checks
from honeywagon.cli import main
from honeywagon.deps import osv
from honeywagon.deps.manifests import Dependency
from honeywagon.deps.osv import Advisory, Lookup, advisories_from, look_up_all
from honeywagon.files import Project
from honeywagon.models import NotChecked
from honeywagon.pipeline import run_audit

SKILL = {"SKILL.md": "---\nname: x\n---\n\n# x\n"}
MODERATE = Advisory("GHSA-aaaa-bbbb-cccc", "MODERATE", ("2.32.4",))
CRITICAL = Advisory("GHSA-dddd-eeee-ffff", "CRITICAL", ())


def declared(project: Project) -> list[tuple[str, str, str | None, int]]:
    return [
        (d.ecosystem, d.name, d.version, d.line) for d in analyse(project).dependencies
    ]


def answering(answers: dict[str, tuple[Advisory, ...] | None]) -> Lookup:
    """Return a lookup that answers by package name, and nothing for the rest."""
    return lambda ecosystem, name, version: answers.get(name, ())


def mcp_config(command: str, *args: str) -> dict[str, str]:
    server = {"command": command, "args": list(args)}
    return {".mcp.json": json.dumps({"mcpServers": {"x": server}}, indent=2)}


# Reading the files that declare dependencies


def test_requirements_file_gives_name_version_and_line(
    make_project: ProjectMaker,
) -> None:
    content = "# for the server\nmcp[cli]==2.3.0\n\nrequests==2.31.0  # http\n"

    project = make_project({"requirements.txt": content})

    assert declared(project) == [
        ("PyPI", "mcp", "2.3.0", 2),
        ("PyPI", "requests", "2.31.0", 4),
    ]


@pytest.mark.parametrize(
    "line",
    [
        "requests",
        "requests>=2.31",
        "requests~=2.31.0",
        "requests==2.*",
        "requests>=2,<3",
        "requests @ https://example.com/requests.whl",
    ],
)
def test_requirement_without_one_exact_version_has_no_version(
    make_project: ProjectMaker, line: str
) -> None:
    project = make_project({"requirements.txt": f"{line}\n"})

    assert declared(project) == [("PyPI", "requests", None, 1)]


@pytest.mark.parametrize(
    "line",
    [
        "-r base.txt",
        "--index-url https://packages.example.com/simple",
        "-e .",
        "https://example.com/pkg.whl",
        "",
    ],
)
def test_lines_that_name_no_package_are_skipped(
    make_project: ProjectMaker, line: str
) -> None:
    project = make_project({"requirements.txt": f"{line}\n"})

    assert declared(project) == []


def test_package_name_is_written_as_the_registry_writes_it(
    make_project: ProjectMaker,
) -> None:
    content = "Flask_SQLAlchemy==3.1.1 ; python_version >= '3.11'\n"

    project = make_project({"requirements-dev.txt": content})

    assert declared(project) == [("PyPI", "flask-sqlalchemy", "3.1.1", 1)]


def test_other_text_files_are_not_read_as_requirements(
    make_project: ProjectMaker,
) -> None:
    project = make_project({"notes.txt": "requests==2.31.0\n"})

    assert declared(project) == []


def test_pyproject_gives_the_dependencies_of_the_project_table(
    make_project: ProjectMaker,
) -> None:
    content = (
        "[project]\n"
        'name = "x"\n'
        "dependencies = [\n"
        '    "mcp[cli]==2.3.0",\n'
        '    "httpx>=0.27",\n'
        "]\n\n"
        "[project.optional-dependencies]\n"
        'dev = ["pytest==8.3.0"]\n\n'
        "[tool.other]\n"
        'dependencies = ["ignored==1.0"]\n'
    )

    project = make_project({"pyproject.toml": content})

    assert declared(project) == [
        ("PyPI", "mcp", "2.3.0", 4),
        ("PyPI", "httpx", None, 5),
        ("PyPI", "pytest", "8.3.0", 9),
    ]


def test_pyproject_that_cannot_be_parsed_is_reported(
    make_project: ProjectMaker,
) -> None:
    project = make_project({"pyproject.toml": "[project\n"})

    assert analyse(project).not_checked == (
        NotChecked("pyproject.toml", "invalid_toml"),
    )


@pytest.mark.parametrize(
    ("command", "args", "expected"),
    [
        ("npx", ("-y", "mcp-remote@0.1.15"), ("npm", "mcp-remote", "0.1.15")),
        ("npx", ("@scope/server@2.0.1",), ("npm", "@scope/server", "2.0.1")),
        ("npx", ("-y", "@scope/server"), ("npm", "@scope/server", None)),
        ("npx", ("some-server@latest",), ("npm", "some-server", None)),
        ("npx", ("some-server@^1.2",), ("npm", "some-server", None)),
        ("pnpm", ("dlx", "some-server@1.2.3"), ("npm", "some-server", "1.2.3")),
        ("uvx", ("Some_Server==1.2.3",), ("PyPI", "some-server", "1.2.3")),
        ("npx.cmd", ("some-server@1.2.3",), ("npm", "some-server", "1.2.3")),
    ],
)
def test_mcp_server_that_is_downloaded_is_a_dependency(
    make_project: ProjectMaker,
    command: str,
    args: tuple[str, ...],
    expected: tuple[str, str, str | None],
) -> None:
    project = make_project(mcp_config(command, *args))

    ((ecosystem, name, version, line),) = declared(project)

    assert (ecosystem, name, version) == expected
    assert args[-1] in project.files[0].lines[line - 1]


def test_mcp_server_that_runs_local_code_is_not_a_dependency(
    make_project: ProjectMaker,
) -> None:
    project = make_project(mcp_config("python", "server.py"))

    assert declared(project) == []


# Reading the answers of the database

RECORDS: list[dict[str, Any]] = [
    {
        "id": "PYSEC-2026-1",
        "aliases": ["CVE-2024-1", "GHSA-aaaa-bbbb-cccc"],
        "affected": [
            {
                "package": {"ecosystem": "PyPI", "name": "requests"},
                "ranges": [{"events": [{"introduced": "0"}, {"fixed": "2.32.4"}]}],
            }
        ],
    },
    {
        "id": "GHSA-aaaa-bbbb-cccc",
        "aliases": ["CVE-2024-1", "PYSEC-2026-1"],
        "database_specific": {"severity": "MODERATE"},
        "affected": [
            {
                "package": {"ecosystem": "PyPI", "name": "Requests"},
                "ranges": [{"events": [{"introduced": "0"}, {"fixed": "2.32.4"}]}],
            },
            {
                "package": {"ecosystem": "Debian", "name": "requests"},
                "ranges": [{"events": [{"fixed": "9.9.9"}]}],
            },
        ],
    },
    {
        "id": "GHSA-dddd-eeee-ffff",
        "database_specific": {"severity": "HIGH"},
        "affected": [
            {
                "package": {"ecosystem": "PyPI", "name": "requests"},
                "ranges": [
                    {"events": [{"introduced": "0"}, {"fixed": "2.10.0"}]},
                    {"events": [{"introduced": "2.20"}, {"fixed": "2.9.1"}]},
                ],
            }
        ],
    },
]


def test_the_same_problem_under_two_ids_is_one_advisory() -> None:
    advisories = advisories_from(RECORDS, "PyPI", "requests")

    assert [advisory.id for advisory in advisories] == [
        "GHSA-aaaa-bbbb-cccc",
        "GHSA-dddd-eeee-ffff",
    ]


def test_advisory_keeps_the_rating_and_the_fixes_of_this_registry_only() -> None:
    first, second = advisories_from(RECORDS, "PyPI", "requests")

    assert (first.rating, first.fixed_in) == ("MODERATE", ("2.32.4",))
    assert (second.rating, second.fixed_in) == ("HIGH", ("2.9.1", "2.10.0"))


def test_advisory_without_a_rating_or_a_fix_says_so() -> None:
    (advisory,) = advisories_from([{"id": "PYSEC-2026-9"}], "PyPI", "requests")

    assert advisory == Advisory("PYSEC-2026-9", None, ())


def test_each_package_is_looked_up_once() -> None:
    asked = []

    def lookup(ecosystem: str, name: str, version: str) -> tuple[Advisory, ...]:
        asked.append((ecosystem, name, version))
        return ()

    package = ("PyPI", "requests", "2.31.0")
    answers = look_up_all([package, package, ("npm", "x", "1.0.0")], lookup)

    assert asked == [("PyPI", "requests", "2.31.0"), ("npm", "x", "1.0.0")]
    assert answers == {package: (), ("npm", "x", "1.0.0"): ()}


# Asking the database: the network is replaced by a fake


class FakeNetwork:
    """Stands in for urlopen: records each request and plays back the answers."""

    def __init__(self, *answers: object):
        self.answers = list(answers)
        self.requests: list[Any] = []

    def __call__(self, request: Any, timeout: float) -> io.BytesIO:
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(json.dumps(answer).encode())


def test_lookup_sends_only_registry_name_and_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    network = FakeNetwork({"vulns": RECORDS})
    monkeypatch.setattr("urllib.request.urlopen", network)

    advisories = osv.osv_lookup("PyPI", "requests", "2.31.0")

    (request,) = network.requests
    assert request.full_url == "https://api.osv.dev/v1/query"
    assert json.loads(request.data) == {
        "package": {"ecosystem": "PyPI", "name": "requests"},
        "version": "2.31.0",
    }
    assert advisories is not None and len(advisories) == 2


def test_lookup_of_a_version_without_problems_gives_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("urllib.request.urlopen", FakeNetwork({}))

    assert osv.osv_lookup("PyPI", "mcp", "2.3.0") == ()


def test_lookup_follows_the_next_page(monkeypatch: pytest.MonkeyPatch) -> None:
    network = FakeNetwork(
        {"vulns": RECORDS[:2], "next_page_token": "abc"}, {"vulns": RECORDS[2:]}
    )
    monkeypatch.setattr("urllib.request.urlopen", network)

    advisories = osv.osv_lookup("PyPI", "requests", "2.31.0")

    assert json.loads(network.requests[1].data)["page_token"] == "abc"
    assert advisories is not None and len(advisories) == 2


@pytest.mark.parametrize(
    "answer", [OSError("no network"), TimeoutError(), ["not", "an", "object"]]
)
def test_lookup_that_fails_gives_none_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch, answer: object
) -> None:
    monkeypatch.setattr("urllib.request.urlopen", FakeNetwork(answer))

    assert osv.osv_lookup("PyPI", "requests", "2.31.0") is None


# The dep-security check

CHECK = next(check for check in load_checks() if check.check_id == "dep-security")


def hits(project: Project, lookup: Lookup | None) -> list[Hit]:
    return list(CHECK.function(analyse(project, lookup), CHECK.options))


def test_dependency_with_a_known_problem_is_found_on_its_line(
    make_project: ProjectMaker,
) -> None:
    project = make_project({"requirements.txt": "mcp==2.3.0\nrequests==2.31.0\n"})

    (hit,) = hits(project, answering({"requests": (MODERATE,)}))

    assert (hit.file, hit.line, hit.evidence) == (
        "requirements.txt",
        2,
        "requests==2.31.0",
    )
    assert hit.severity is None
    assert hit.values == {"count": "1", "advisories": "GHSA-aaaa-bbbb-cccc (2.32.4)"}


def test_problem_that_the_database_rates_critical_is_critical(
    make_project: ProjectMaker,
) -> None:
    project = make_project(mcp_config("npx", "-y", "mcp-remote@0.1.15"))

    (hit,) = hits(project, answering({"mcp-remote": (MODERATE, CRITICAL)}))

    assert hit.severity == "critical"
    assert hit.values == {
        "count": "2",
        "advisories": "GHSA-aaaa-bbbb-cccc (2.32.4), GHSA-dddd-eeee-ffff (-)",
    }


@pytest.mark.parametrize(
    "lookup",
    [None, answering({}), answering({"requests": None})],
    ids=["no lookup", "no known problem", "lookup failed"],
)
def test_dependency_without_a_known_problem_is_not_flagged(
    make_project: ProjectMaker, lookup: Lookup | None
) -> None:
    project = make_project({"requirements.txt": "requests==2.31.0\n"})

    assert hits(project, lookup) == []


def test_dependency_without_an_exact_version_is_never_looked_up(
    make_project: ProjectMaker,
) -> None:
    asked = []

    def lookup(ecosystem: str, name: str, version: str) -> tuple[Advisory, ...]:
        asked.append(name)
        return (MODERATE,)

    project = make_project({"requirements.txt": "requests>=2\n"})

    assert hits(project, lookup) == []
    assert asked == []


# The whole audit


def audit(tmp_path: Path, files: dict[str, str], lookup: Lookup | None = None) -> Any:
    for path, content in {**SKILL, **files}.items():
        (tmp_path / path).write_text(content, encoding="utf-8")
    return run_audit(tmp_path, lookup)


def not_checked(result: Any) -> dict[str, str]:
    return {item.reason: item.what for item in result.not_checked}


def test_finding_lists_the_problems_and_takes_its_severity_from_the_rating(
    tmp_path: Path,
) -> None:
    files = {"requirements.txt": "requests==2.31.0\n", **mcp_config("npx", "x@1.0.0")}
    lookup = answering({"requests": (MODERATE,), "x": (CRITICAL,)})

    critical, error = audit(tmp_path, files, lookup).findings

    assert (critical.check_id, critical.file, critical.severity) == (
        "dep-security",
        ".mcp.json",
        "critical",
    )
    assert (error.file, error.severity, error.fix_effort) == (
        "requirements.txt",
        "error",
        "simple",
    )
    assert "(1): GHSA-aaaa-bbbb-cccc (2.32.4)." in error.consequence
    assert error.suggestion is None


def test_without_a_lookup_the_names_that_would_be_sent_are_listed(
    tmp_path: Path,
) -> None:
    files = {"requirements.txt": "requests==2.31.0\nmcp==2.3.0\nhttpx>=0.27\n"}

    result = audit(tmp_path, files)

    assert result.findings == ()
    assert result.looked_up == ()
    reasons = not_checked(result)
    assert reasons["dependency_lookup_off"] == "requests 2.31.0, mcp 2.3.0"
    assert reasons["dependency_not_pinned"] == "httpx"
    assert reasons["indirect_dependencies"] == "Indirect dependencies"
    assert "dependency_lookup_failed" not in reasons


def test_with_a_lookup_the_result_says_what_was_sent(tmp_path: Path) -> None:
    files = {"requirements.txt": "requests==2.31.0\nhttpx>=0.27\n"}

    result = audit(tmp_path, files, answering({}))

    assert result.looked_up == ("PyPI requests 2.31.0",)
    assert "dependency_lookup_off" not in not_checked(result)
    assert not_checked(result)["dependency_not_pinned"] == "httpx"


def test_lookup_that_failed_is_reported_and_the_audit_goes_on(
    tmp_path: Path,
) -> None:
    files = {"requirements.txt": "requests==2.31.0\nmcp==2.3.0\n"}

    result = audit(tmp_path, files, answering({"requests": None}))

    assert result.findings == ()
    assert not_checked(result)["dependency_lookup_failed"] == "requests 2.31.0"


def test_project_without_dependencies_says_nothing_about_them(
    tmp_path: Path,
) -> None:
    result = audit(tmp_path, {})

    assert not any("depend" in reason for reason in not_checked(result))


# The command


def test_command_asks_the_database_only_with_the_lookup_option(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    asked = []

    def lookup(ecosystem: str, name: str, version: str) -> tuple[Advisory, ...]:
        asked.append(name)
        return (MODERATE,)

    monkeypatch.setattr("honeywagon.cli.osv_lookup", lookup)
    for path, content in {**SKILL, "requirements.txt": "requests==2.31.0\n"}.items():
        (tmp_path / path).write_text(content, encoding="utf-8")

    main([str(tmp_path)])
    without = capsys.readouterr().out
    main([str(tmp_path), "--lookup"])
    with_lookup = capsys.readouterr().out

    assert asked == ["requests"]
    assert "Run again with --lookup" in without
    assert "Sent to the OSV database" not in without
    assert "Sent to the OSV database: PyPI requests 2.31.0" in with_lookup
    assert "A dependency has a known security problem" in with_lookup


# The recorded answers that the evaluation uses


def test_every_dependency_of_the_fixtures_has_a_recorded_answer() -> None:
    fixtures = evaluate.load_fixtures(evaluate.FIXTURES_DIR)
    lookup = evaluate.recorded_lookup()

    for package in evaluate.fixture_packages(fixtures):
        assert lookup(*package) is not None, package


def test_recorded_answers_give_the_planted_severities() -> None:
    lookup = evaluate.recorded_lookup()

    agent = run_audit(fixture_project("agent-support-triage"), lookup)
    plugin = run_audit(fixture_project("plugin-team-helper"), lookup)

    assert {f.check_id: f.severity for f in agent.findings}["dep-security"] == "error"
    assert {(f.check_id, f.file): f.severity for f in plugin.findings}[
        "dep-security", ".mcp.json"
    ] == "critical"


def test_dependency_is_named_with_its_version_when_it_has_one() -> None:
    assert (
        Dependency("PyPI", "requests", "2.31.0", "r.txt", 1).label == "requests 2.31.0"
    )
    assert Dependency("PyPI", "requests", None, "r.txt", 1).label == "requests"
