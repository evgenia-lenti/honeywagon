"""Checks for file paths, unsafe loading, TLS and remote MCP servers."""

import json
from pathlib import Path

import pytest
from conftest import ProjectMaker
from test_checks import BODY_LINE, mcp_tool, places, run

from honeywagon.capability import analyse, capability_map
from honeywagon.guard.redact import address, mask
from honeywagon.pipeline import run_audit
from honeywagon.report import render_json, render_text
from honeywagon.triage import risk_map

TOKEN = "mtk_" + "FAKE-FIXTURE-NOT-A-REAL-TOKEN"


def remote_server(url: str, headers: dict[str, str] | None = None) -> dict[str, str]:
    server: dict[str, object] = {"type": "http", "url": url}
    if headers is not None:
        server["headers"] = headers
    return {".mcp.json": json.dumps({"mcpServers": {"wiki": server}}, indent=2)}


# inject-path


@pytest.mark.parametrize(
    "body",
    [
        'with open(f"exports/{value}") as handle:\n    return handle.read()',
        "with open(value) as handle:\n    return handle.read()",
        'return (Path("exports") / value).read_text()',
        'Path("exports", value).write_text("x")\nreturn "ok"',
    ],
    ids=["part of the path", "whole path", "read_text", "write_text"],
)
def test_tool_input_that_becomes_a_file_path_is_found(
    make_project: ProjectMaker, body: str
) -> None:
    project = make_project(mcp_tool(body))

    assert places("inject-path", project) == [("server.py", BODY_LINE)]


def test_path_through_a_local_name_is_found_where_the_file_is_opened(
    make_project: ProjectMaker,
) -> None:
    body = (
        'target = "exports/" + value\n'
        "with open(target) as handle:\n"
        "    return handle.read()"
    )
    project = make_project(mcp_tool(body))

    assert places("inject-path", project) == [("server.py", BODY_LINE + 1)]


@pytest.mark.parametrize(
    "body",
    [
        'with open("exports/latest.csv") as handle:\n    return handle.read()',
        (
            'path = (Path("exports") / value).resolve()\n'
            'if not path.is_relative_to(Path("exports").resolve()):\n'
            '    raise ValueError("outside")\n'
            "return path.read_text()"
        ),
        'return open(os.path.join("exports", os.path.basename(value))).read()',
        'return open(f"exports/{int(value)}.csv").read()',
    ],
    ids=["fixed path", "is_relative_to", "basename", "number"],
)
def test_path_that_is_fixed_or_kept_in_its_folder_is_not_flagged(
    make_project: ProjectMaker, body: str
) -> None:
    project = make_project(mcp_tool(body))

    assert run("inject-path", project) == []


# inject-deserialization


@pytest.mark.parametrize(
    "body",
    [
        "return str(pickle.loads(value))",
        "return str(pickle.loads(base64.b64decode(value)))",
        "return str(yaml.load(value))",
        "return str(yaml.load(value, Loader=yaml.Loader))",
        "return str(yaml.unsafe_load(value))",
        'return str(pickle.load(open(value, "rb")))',
    ],
    ids=["pickle", "decoded first", "yaml", "yaml full loader", "unsafe_load", "file"],
)
def test_tool_input_that_is_loaded_unsafely_is_found(
    make_project: ProjectMaker, body: str
) -> None:
    project = make_project(mcp_tool(body))

    assert places("inject-deserialization", project) == [("server.py", BODY_LINE)]


@pytest.mark.parametrize(
    "body",
    [
        "return str(json.loads(value))",
        "return str(yaml.safe_load(value))",
        "return str(yaml.load(value, Loader=yaml.SafeLoader))",
        "return str(yaml.load(value, SafeLoader))",
        'return str(pickle.load(open("cache.bin", "rb")))',
    ],
    ids=["json", "safe_load", "safe loader", "safe loader by place", "own file"],
)
def test_safe_loading_or_loading_of_own_data_is_not_flagged(
    make_project: ProjectMaker, body: str
) -> None:
    project = make_project(mcp_tool(body))

    assert run("inject-deserialization", project) == []


# net-tls-off


@pytest.mark.parametrize(
    "line",
    [
        "requests.get(URL, verify=False)",
        "client = httpx.Client(verify=False)",
        "session.post(URL, json=data, verify=False)",
        "context = ssl._create_unverified_context()",
    ],
)
def test_switched_off_tls_verification_is_found_in_any_python_file(
    make_project: ProjectMaker, line: str
) -> None:
    files = {"SKILL.md": "# x", "scripts/send.py": f"import requests\n\n{line}\n"}

    assert places("net-tls-off", make_project(files)) == [("scripts/send.py", 3)]


def test_evidence_is_the_line_that_switches_verification_off(
    make_project: ProjectMaker,
) -> None:
    code = "import requests\n\nrequests.post(\n    URL,\n    verify=False,\n)\n"
    project = make_project({"SKILL.md": "# x", "send.py": code})

    (hit,) = run("net-tls-off", project)

    assert (hit.line, hit.evidence.strip()) == (5, "verify=False,")


@pytest.mark.parametrize(
    "line",
    [
        "requests.get(URL)",
        "requests.get(URL, verify=True)",
        'requests.get(URL, verify="company-ca.pem")',
        "requests.get(URL, verify=VERIFY)",
        "token = decode(value, verify=False)",
        "context = ssl.create_default_context()",
    ],
)
def test_verified_or_unrelated_calls_are_not_flagged(
    make_project: ProjectMaker, line: str
) -> None:
    files = {"SKILL.md": "# x", "send.py": f"import requests\n\n{line}\n"}

    assert run("net-tls-off", make_project(files)) == []


# mcp-plain-http


def test_remote_server_without_encryption_is_found(
    make_project: ProjectMaker,
) -> None:
    project = make_project(remote_server("http://wiki.example.com/mcp"))

    (hit,) = run("mcp-plain-http", project)

    assert (hit.file, hit.line) == (".mcp.json", 5)
    assert hit.evidence.strip() == '"url": "http://wiki.example.com/mcp"'


@pytest.mark.parametrize(
    "url",
    [
        "https://wiki.example.com/mcp",
        "http://localhost:8080/mcp",
        "http://127.0.0.1:8080/mcp",
        "http://[::1]:8080/mcp",
        "${WIKI_URL}/mcp",
        "${WIKI_URL:-http://wiki.example.com}/mcp",
    ],
)
def test_encrypted_local_or_unknown_address_is_not_flagged(
    make_project: ProjectMaker, url: str
) -> None:
    assert run("mcp-plain-http", make_project(remote_server(url))) == []


def test_password_in_the_address_is_not_shown_as_evidence(
    make_project: ProjectMaker,
) -> None:
    url = "http://team:" + TOKEN + "@wiki.example.com/mcp?key=" + TOKEN

    (hit,) = run("mcp-plain-http", make_project(remote_server(url)))

    assert TOKEN not in hit.evidence
    assert "http://wiki.example.com/mcp" in hit.evidence


# secret-in-file: a key in a header of a remote server


@pytest.mark.parametrize(
    ("header", "value"),
    [
        ("Authorization", f"Bearer {TOKEN}"),
        ("authorization", TOKEN),
        ("X-API-Key", TOKEN),
    ],
)
def test_key_written_in_a_header_is_found_and_hidden(
    make_project: ProjectMaker, header: str, value: str
) -> None:
    project = make_project(
        remote_server("https://wiki.example.com/mcp", {header: value})
    )

    (hit,) = run("secret-in-file", project)

    assert (hit.file, hit.line) == (".mcp.json", 7)
    assert TOKEN not in hit.evidence
    assert "mtk_FA...REDACTED" in hit.evidence


@pytest.mark.parametrize(
    ("header", "value"),
    [
        ("Authorization", "Bearer ${WIKI_TOKEN}"),
        ("X-API-Key", "${WIKI_KEY:-}"),
        ("X-Team", "platform"),
        ("Authorization", ""),
    ],
)
def test_header_from_the_environment_or_without_a_key_is_not_flagged(
    make_project: ProjectMaker, header: str, value: str
) -> None:
    project = make_project(
        remote_server("https://wiki.example.com/mcp", {header: value})
    )

    assert run("secret-in-file", project) == []


def test_key_of_a_known_shape_in_a_header_is_reported_once(
    make_project: ProjectMaker,
) -> None:
    key = "ghp_" + "FAKE-FIXTURE-NOT-A-REAL-TOKEN"
    headers = {"Authorization": f"Bearer {key}"}
    project = make_project(remote_server("https://wiki.example.com/mcp", headers))

    assert len(run("secret-in-file", project)) == 1


def test_key_in_a_header_reaches_no_output(tmp_path: Path) -> None:
    files = remote_server("https://wiki.example.com/mcp", {"X-API-Key": TOKEN})
    for path, content in {"SKILL.md": "# x", **files}.items():
        (tmp_path / path).write_text(content, encoding="utf-8")

    result = run_audit(tmp_path)

    assert [finding.check_id for finding in result.findings] == ["secret-in-file"]
    assert "FAKE-FIXTURE" not in render_json(result)
    assert "FAKE-FIXTURE" not in render_text(result)


# Hiding a secret that has no known shape


def test_mask_shows_the_start_of_a_long_secret_only() -> None:
    assert mask("key: abcdefghijklmnopqrstuvwxyz", "abcdefghijklmnopqrstuvwxyz") == (
        "key: abcdef...REDACTED"
    )


def test_mask_shows_less_of_a_short_secret() -> None:
    assert mask("key: abc123", "abc123") == "key: ab...REDACTED"


@pytest.mark.parametrize(
    ("url", "shown"),
    [
        (
            "https://user:pass@wiki.example.com/mcp?key=1#x",
            "https://wiki.example.com/mcp",
        ),
        ("https://wiki.example.com:8443/mcp", "https://wiki.example.com:8443/mcp"),
        ("${WIKI_URL}/mcp", "${WIKI_URL}/mcp"),
    ],
)
def test_address_keeps_only_scheme_host_and_path(url: str, shown: str) -> None:
    assert address(url) == shown


# Remote servers in the map, in the risk map and in "not checked"


def test_remote_server_is_marked_and_shown_without_its_secrets(
    make_project: ProjectMaker,
) -> None:
    url = "https://team:" + TOKEN + "@wiki.example.com/mcp"
    capabilities = capability_map(analyse(make_project(remote_server(url))))

    (server,) = capabilities.mcp_servers
    (group,) = risk_map(capabilities).groups

    assert (server.remote, server.command) == (True, "https://wiki.example.com/mcp")
    assert [(reason.key, reason.items) for reason in group.reasons] == [
        ("connects_to_remote_server", ("wiki",))
    ]


def test_whether_a_remote_server_asks_who_is_calling_is_not_checked(
    tmp_path: Path,
) -> None:
    files = remote_server("https://wiki.example.com/mcp")
    for path, content in {"SKILL.md": "# x", **files}.items():
        (tmp_path / path).write_text(content, encoding="utf-8")

    result = run_audit(tmp_path)

    assert result.findings == ()
    assert ("wiki", "remote_server_authentication") in {
        (item.what, item.reason) for item in result.not_checked
    }
