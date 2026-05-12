import pytest
from pydantic import ValidationError
from agent.models import Finding, ReviewReport, Severity


def test_valid_finding():
    f = Finding(
        severity=Severity.HIGH,
        category="security",
        file_path="src/auth.py",
        description="Missing input validation",
        suggestion="Add Pydantic validator",
    )
    assert f.severity == Severity.HIGH


def test_valid_empty_report():
    report = ReviewReport(
        pr_url="https://github.com/owner/repo/pull/1",
        summary="No issues found",
        findings=[],
        risk_score=0.0,
        model_used="gpt-4o-mini",
        tokens_used=100,
        cached=False,
    )
    assert report.risk_score == 0.0


def test_risk_score_too_high():
    with pytest.raises(ValidationError):
        ReviewReport(
            pr_url="https://github.com/owner/repo/pull/1",
            summary="test",
            findings=[],
            risk_score=11.0,
            model_used="gpt-4o-mini",
            tokens_used=100,
            cached=False,
        )


def test_risk_score_negative():
    with pytest.raises(ValidationError):
        ReviewReport(
            pr_url="https://github.com/owner/repo/pull/1",
            summary="test",
            findings=[],
            risk_score=-1.0,
            model_used="gpt-4o-mini",
            tokens_used=100,
            cached=False,
        )
