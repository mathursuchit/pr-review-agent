import asyncio
import pytest
from agent.nodes.guardrails import run


def _valid_report(pr_url: str = "https://github.com/owner/repo/pull/1") -> dict:
    return {
        "pr_url": pr_url,
        "summary": "One issue found",
        "findings": [],
        "risk_score": 3.0,
        "model_used": "gpt-4o",
        "tokens_used": 500,
        "cached": False,
    }


def test_passes_valid_report():
    state = {
        "final_report": _valid_report(),
        "raw_diff": "diff --git a/src/main.py b/src/main.py",
        "retry_count": 0,
    }
    result = asyncio.run(run(state))
    assert result["guardrail_passed"] is True


def test_fails_missing_report():
    state = {"final_report": None, "raw_diff": "", "retry_count": 0}
    result = asyncio.run(run(state))
    assert result["guardrail_passed"] is False
    assert result["retry_count"] == 1


def test_corrects_hallucinated_path():
    report = _valid_report()
    report["findings"] = [{
        "severity": "high",
        "category": "security",
        "file_path": "src/does_not_exist.py",
        "line_range": None,
        "description": "test",
        "suggestion": "fix it",
    }]
    state = {
        "final_report": report,
        "raw_diff": "diff --git a/src/main.py",
        "retry_count": 0,
    }
    result = asyncio.run(run(state))
    assert result["guardrail_passed"] is True
    assert result["final_report"]["findings"][0]["file_path"] == "unknown"
