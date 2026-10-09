"""Confidence and the proposed verdict. Both come from fixed rules, never a model."""

from collections.abc import Sequence

from honeywagon.models import Finding, Origin

COUNTING_CONFIDENCES = frozenset({"high", "medium"})


def confidence_of(origin: Origin, verification: str | None) -> str:
    """Derive the confidence from where a finding came from."""
    if origin.layer == "deterministic":
        return "high"
    if verification == "confirmed":
        return "medium"
    return "low"


def propose_verdict(findings: Sequence[Finding]) -> tuple[str, tuple[str, ...]]:
    """Return the key of the verdict and the ids of the findings that caused it.

    A critical finding gives "not recommended for use". An error without a
    critical gives "fix before use". Low-confidence findings do not count.
    """
    counting = [f for f in findings if f.confidence in COUNTING_CONFIDENCES]
    for severity, key in (("critical", "not_recommended"), ("error", "fix_before_use")):
        triggered_by = tuple(f.id for f in counting if f.severity == severity)
        if triggered_by:
            return key, triggered_by
    return "no_reason_found", ()
