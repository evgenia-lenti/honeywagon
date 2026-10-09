"""The report of one audit, for a machine or for a person."""

from honeywagon.report.json_report import render_json
from honeywagon.report.text_report import render_text

__all__ = ["render_json", "render_text"]
