"""Dependencies with a published security problem."""

from collections.abc import Iterator, Mapping
from typing import Any

from honeywagon.capability import Analysis
from honeywagon.checks.registry import Hit, register


@register("dep-security")
def known_problem(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
    # Without a lookup nothing is known, and the pipeline reports it as not checked.
    for dependency in analysis.dependencies:
        advisories = analysis.advisories.get(dependency.package)
        if not advisories:
            continue
        file = analysis.project.file(dependency.file)
        assert file is not None
        is_critical = any(a.rating in options["critical_ratings"] for a in advisories)
        listed = [
            f"{advisory.id} ({', '.join(advisory.fixed_in) or options['no_fix_mark']})"
            for advisory in advisories
        ]
        yield Hit(
            file=dependency.file,
            line=dependency.line,
            evidence=file.lines[dependency.line - 1],
            severity="critical" if is_critical else None,
            values={"count": str(len(advisories)), "advisories": ", ".join(listed)},
        )
