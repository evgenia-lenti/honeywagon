"""Files that a skill points to."""

import posixpath
import re
from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.capability.config_files import SKILL_FILE
from honeywagon.checks.registry import Hit, register

# ${CLAUDE_SKILL_DIR}/scripts/run.sh
SKILL_DIR_PATH = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/([\w./-]+)")
# [text](path) and [text](path#section)
MARKDOWN_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
NOT_A_FILE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|/|\$|<)", re.IGNORECASE)


def referenced_paths(line: str) -> list[str]:
    """Return the paths a line refers to, relative to the skill's folder."""
    paths = [path.rstrip(".") for path in SKILL_DIR_PATH.findall(line)]
    paths += [
        path for path in MARKDOWN_LINK.findall(line) if not NOT_A_FILE.match(path)
    ]
    return paths


@register("ref-missing-file")
def missing_file(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    project = analysis.project
    for file in project.named(SKILL_FILE):
        for number, line in enumerate(file.lines, start=1):
            for path in referenced_paths(line):
                target = posixpath.normpath(posixpath.join(file.folder, path))
                if target.startswith("..") or project.exists(target):
                    continue
                yield Hit(file.path, number, line)
                break
