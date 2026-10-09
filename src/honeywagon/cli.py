"""The `audit` command."""

import argparse
import io
import sys
from collections.abc import Sequence
from pathlib import Path

from honeywagon.classify import COUNTING_CONFIDENCES
from honeywagon.models import RunResult
from honeywagon.pipeline import run_audit
from honeywagon.report import render_json, render_text

# A usage error exits with 2, which argparse does by itself.
EXIT_OK = 0
EXIT_CRITICAL = 1


def exit_code(result: RunResult) -> int:
    """Signal a critical finding to a calling script. It blocks nothing."""
    has_critical = any(
        finding.severity == "critical" and finding.confidence in COUNTING_CONFIDENCES
        for finding in result.findings
    )
    return EXIT_CRITICAL if has_critical else EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audit",
        description="Audit a skill, plugin, MCP server or agent. Read-only, advisory.",
    )
    parser.add_argument("folder", type=Path, help="the project folder to audit")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="text for a person (default), json for a machine",
    )
    args = parser.parse_args(argv)
    if not args.folder.is_dir():
        parser.error(f"not a folder: {args.folder}")

    result = run_audit(args.folder)
    report = render_json(result) if args.format == "json" else render_text(result)
    # Evidence can hold characters that the terminal's encoding cannot show.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="backslashreplace")
    print(report)
    return exit_code(result)
