"""Find secrets and keep them out of every output."""

import re
from functools import cache

from honeywagon.datafiles import load_data

VISIBLE_CHARACTERS = 6
REDACTED = "...REDACTED"
MAX_EVIDENCE_LENGTH = 200
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


@cache
def _secret_pattern() -> re.Pattern[str]:
    patterns = load_data("secret_patterns.toml")["pattern"]
    return re.compile("|".join(f"(?:{pattern['regex']})" for pattern in patterns))


def contains_secret(text: str) -> bool:
    return _secret_pattern().search(text) is not None


def redact(text: str) -> str:
    """Replace every secret with its first characters and a marker."""
    return _secret_pattern().sub(
        lambda match: match.group()[:VISIBLE_CHARACTERS] + REDACTED, text
    )


def safe_evidence(text: str) -> str:
    """Make a line from an audited file safe to show: no secrets, one short line."""
    cleaned = CONTROL_CHARACTERS.sub(" ", redact(text)).strip()
    if len(cleaned) > MAX_EVIDENCE_LENGTH:
        return cleaned[:MAX_EVIDENCE_LENGTH] + "..."
    return cleaned
