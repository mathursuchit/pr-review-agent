import structlog
from agent.state import ReviewState
from agent.tools.injection_guard import check_injection
from agent.tools.secrets_scan import scan_secrets, redact_secrets

logger = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    if state.get("error"):
        return {"injection_flagged": False, "secrets_found": []}

    diff = state["raw_diff"]
    injection = check_injection(diff)
    secrets = scan_secrets(diff)

    if secrets:
        logger.warning("secrets_detected", types=secrets, pr_url=state["pr_url"])
        diff = redact_secrets(diff)

    if injection:
        logger.warning("injection_detected", pr_url=state["pr_url"])

    return {
        "injection_flagged": injection,
        "secrets_found": secrets,
        "raw_diff": diff,
    }


async def reject(state: ReviewState) -> dict:
    logger.warning("review_rejected_injection", pr_url=state["pr_url"])
    return {"error": "Prompt injection detected in PR diff. Review aborted.", "final_report": None}
