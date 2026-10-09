import pytest

from honeywagon.guard.redact import contains_secret, redact, safe_evidence

# Built from pieces so that this file holds nothing that looks like a key.
FAKE_ANTHROPIC = "sk-ant-" + "api03-FAKE-FIXTURE-NOT-A-REAL-KEY"
FAKE_GITHUB = "ghp_" + "FAKE-FIXTURE-NOT-A-REAL-TOKEN"
FAKE_SLACK = "xoxb-" + "FAKE-FIXTURE-NOT-A-REAL-TOKEN"


@pytest.mark.parametrize("secret", [FAKE_ANTHROPIC, FAKE_GITHUB, FAKE_SLACK])
def test_secret_is_recognised_and_redacted(secret: str) -> None:
    line = f'TOKEN = "{secret}"'

    assert contains_secret(line)
    assert secret not in redact(line)
    assert redact(line) == f'TOKEN = "{secret[:6]}...REDACTED"'


@pytest.mark.parametrize(
    "line",
    [
        '"NOTES_DB": "${CLAUDE_PLUGIN_DATA}/notes.db"',
        '"Authorization": "Bearer ${API_TOKEN}"',
        "api_key = os.environ['ANTHROPIC_API_KEY']",
        "the task-force-meeting-notes-for-the-whole-platform-team file",
    ],
)
def test_text_without_a_secret_is_left_alone(line: str) -> None:
    assert not contains_secret(line)
    assert redact(line) == line


def test_evidence_is_one_short_line_without_control_characters() -> None:
    evidence = safe_evidence("  a\tb\x1b[31m" + "x" * 500)

    assert "\t" not in evidence
    assert "\x1b" not in evidence
    assert len(evidence) < 210
    assert evidence.endswith("...")
