from typing import TypedDict


class ReviewState(TypedDict):
    pr_url: str
    raw_diff: str
    chunks: list[str]
    injection_flagged: bool
    secrets_found: list[str]
    security_findings: list[dict]
    logic_findings: list[dict]
    test_findings: list[dict]
    final_report: dict | None
    guardrail_passed: bool
    retry_count: int
    error: str | None
