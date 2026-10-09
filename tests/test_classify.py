from honeywagon.classify import confidence_of, propose_verdict
from honeywagon.models import Finding, Origin


def finding(identifier: str, severity: str, confidence: str = "high") -> Finding:
    return Finding(
        id=identifier,
        check_id="sample-check",
        title="",
        file="SKILL.md",
        line=1,
        evidence="",
        consequence="",
        severity=severity,
        confidence=confidence,
        fix_effort="simple",
        suggestion=None,
        origin=Origin("deterministic", "checks.sample"),
        verification=None,
    )


def test_deterministic_finding_has_high_confidence() -> None:
    assert confidence_of(Origin("deterministic", "checks.secrets"), None) == "high"


def test_model_finding_is_medium_only_when_the_verifier_confirmed_it() -> None:
    origin = Origin("model", "checker.access")

    assert confidence_of(origin, "confirmed") == "medium"
    assert confidence_of(origin, "uncertain") == "low"
    assert confidence_of(origin, None) == "low"


def test_critical_finding_gives_not_recommended() -> None:
    findings = [
        finding("a", "error"),
        finding("b", "critical"),
        finding("c", "critical"),
    ]

    assert propose_verdict(findings) == ("not_recommended", ("b", "c"))


def test_error_without_critical_gives_fix_before_use() -> None:
    findings = [finding("a", "warning"), finding("b", "error")]

    assert propose_verdict(findings) == ("fix_before_use", ("b",))


def test_warnings_alone_give_no_reason_found() -> None:
    assert propose_verdict([finding("a", "warning")]) == ("no_reason_found", ())
    assert propose_verdict([]) == ("no_reason_found", ())


def test_low_confidence_findings_do_not_count() -> None:
    findings = [finding("a", "critical", "low"), finding("b", "error", "medium")]

    assert propose_verdict(findings) == ("fix_before_use", ("b",))
