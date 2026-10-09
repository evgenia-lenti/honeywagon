"""Find secrets and keep them out of every output."""

import re
from functools import cache
from urllib.parse import urlsplit

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


def mask(text: str, secret: str) -> str:
    """Hide one known secret in a text, for a secret that has no known shape.

    A short secret shows fewer characters, so that most of it stays hidden.
    """
    visible = min(VISIBLE_CHARACTERS, len(secret) // 3)
    return text.replace(secret, secret[:visible] + REDACTED)


def address(url: str) -> str:
    """Return an address without the parts that can hold a secret: the user
    name and password in front of the host, and whatever follows a question mark."""
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return url
    host = parts.netloc.rpartition("@")[2]
    return f"{parts.scheme}://{host}{parts.path}"


def safe_evidence(text: str) -> str:
    """Make a line from an audited file safe to show: no secrets, one short line."""
    cleaned = CONTROL_CHARACTERS.sub(" ", redact(text)).strip()
    if len(cleaned) > MAX_EVIDENCE_LENGTH:
        return cleaned[:MAX_EVIDENCE_LENGTH] + "..."
    return cleaned
