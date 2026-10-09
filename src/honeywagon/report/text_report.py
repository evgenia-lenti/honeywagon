"""The report a person reads: verdict, then findings, then what was not checked."""

from itertools import groupby

from honeywagon.datafiles import load_texts
from honeywagon.models import SEVERITIES, RunResult

# Files that were not read are listed up to this number, then counted.
MAX_LISTED_PER_REASON = 10


def render_text(result: RunResult, language: str = "en") -> str:
    texts = load_texts(language)
    labels = texts["report"]
    none = labels["none"]
    lines = [labels["title"], labels["advisory"], ""]
    kinds = ", ".join(texts["kinds"][kind] for kind in result.project_kinds)
    lines.append(f"{labels['project_kinds']}: {kinds or none}")
    lines.append(f"{labels['layers_ran']}: {', '.join(result.layers_ran) or none}")
    lines.append(f"{labels['checks_ran']}: {', '.join(result.checks_ran) or none}")

    lines += ["", f"{labels['proposed_verdict']}: {result.verdict.text}"]
    if result.verdict.partial:
        lines.append(labels["partial"])
    if result.verdict.triggered_by:
        lines.append(
            f"{labels['because_of']}: {', '.join(result.verdict.triggered_by)}"
        )

    lines += ["", labels["findings"]]
    if not result.findings:
        lines.append(f"  {labels['no_findings']}")
    for severity in SEVERITIES:
        findings = [f for f in result.findings if f.severity == severity]
        if not findings:
            continue
        lines += ["", f"  {texts['severity'][severity]}"]
        for finding in findings:
            lines += [
                f"    {finding.title}",
                f"      {finding.file}:{finding.line}  [{finding.id}]  "
                f"{labels['confidence']}: {finding.confidence}  "
                f"{labels['fix']}: {finding.fix_effort}",
                f"      > {finding.evidence}",
                f"      {finding.consequence}",
            ]

    lines += ["", labels["not_checked"]]
    by_reason = sorted(result.not_checked, key=lambda item: item.reason)
    for reason, group in groupby(by_reason, key=lambda item: item.reason):
        items = [item.what for item in group]
        listed = items[:MAX_LISTED_PER_REASON]
        if len(items) > len(listed):
            listed.append(labels["more_files"].format(count=len(items) - len(listed)))
        lines.append(f"  - {', '.join(listed)}: {texts['not_checked'][reason]}")
    return "\n".join(lines)
