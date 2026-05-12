import structlog
from agent.models import ReviewReport
from agent.state import ReviewState

logger = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    report = state.get("final_report")
    retry_count = state.get("retry_count", 0)

    if not report:
        logger.warning("guardrail_no_report", retry_count=retry_count)
        return {"guardrail_passed": False, "retry_count": retry_count + 1}

    # Schema validation
    try:
        validated = ReviewReport(**report)
    except Exception as e:
        logger.warning("guardrail_schema_fail", error=str(e), retry_count=retry_count)
        return {"guardrail_passed": False, "retry_count": retry_count + 1}

    # Hallucination check: verify cited file paths appear in the diff
    diff = state.get("raw_diff", "")
    corrected_findings = []
    for finding in validated.findings:
        if finding.file_path and finding.file_path not in diff and finding.file_path != "unknown":
            logger.warning("guardrail_hallucinated_path", file_path=finding.file_path)
            finding = finding.model_copy(update={"file_path": "unknown"})
        corrected_findings.append(finding)

    validated = validated.model_copy(update={"findings": corrected_findings})
    return {"guardrail_passed": True, "final_report": validated.model_dump()}
