"""The `audit` command."""

import argparse
import io
import sys
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

from honeywagon.classify import COUNTING_CONFIDENCES
from honeywagon.deps.osv import osv_lookup
from honeywagon.models import RunResult
from honeywagon.pipeline import run_audit
from honeywagon.report import render_json, render_markdown, render_text

# A usage error exits with 2, which argparse does by itself.
EXIT_OK = 0
EXIT_CRITICAL = 1

RENDERERS = {"text": render_text, "json": render_json, "markdown": render_markdown}


def exit_code(result: RunResult) -> int:
    """Signal a critical finding to a calling script. It blocks nothing."""
    has_critical = any(
        finding.severity == "critical" and finding.confidence in COUNTING_CONFIDENCES
        for finding in result.findings
    )
    return EXIT_CRITICAL if has_critical else EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit",
        description="Audit a skill, plugin, MCP server or agent. Read-only, advisory.",
    )
    parser.add_argument("folder", type=Path, help="the project folder to audit")
    parser.add_argument(
        "--format",
        choices=tuple(RENDERERS),
        default="text",
        help="text for a terminal (default), markdown for a conversation or a "
        "document, json for a machine",
    )
    parser.add_argument(
        "--lookup",
        action="store_true",
        help="ask the OSV database about known security problems of the "
        "dependencies. This sends their names and versions to api.osv.dev, "
        "and nothing else. Without it nothing is sent anywhere",
    )
    parser.add_argument(
        "--exit-zero",
        action="store_true",
        help="exit with 0 also when a critical finding exists, for a caller "
        "that shows every other exit code as a failure",
    )
    parser.add_argument(
        "--version", action="version", version=f"honeywagon {version('honeywagon')}"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.folder.is_dir():
        parser.error(f"not a folder: {args.folder}")

    result = run_audit(args.folder, osv_lookup if args.lookup else None)
    report = RENDERERS[args.format](result)
    if isinstance(sys.stdout, io.TextIOWrapper):
        # A terminal keeps its own encoding, and a character it cannot show is
        # written as an escape. A pipe or a file gets UTF-8: whoever reads the
        # report there, such as Claude Code, expects that and not the encoding
        # of this computer.
        encoding = None if sys.stdout.isatty() else "utf-8"
        sys.stdout.reconfigure(encoding=encoding, errors="backslashreplace")
    print(report)
    return EXIT_OK if args.exit_zero else exit_code(result)
