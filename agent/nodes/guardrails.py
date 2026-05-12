import structlog
from agent.models import ResearchReport
from agent.state import ResearchState

logger = structlog.get_logger()


async def run(state: ResearchState) -> dict:
    report = state.get("final_report")
    retry_count = state.get("retry_count", 0)

    if not report:
        logger.warning("guardrail_no_report", retry_count=retry_count)
        return {"guardrail_passed": False, "retry_count": retry_count + 1}

    try:
        validated = ResearchReport(**report)
    except Exception as e:
        logger.warning("guardrail_schema_fail", error=str(e))
        return {"guardrail_passed": False, "retry_count": retry_count + 1}

    # Citation hallucination check — drop any cited URL not in scored_sources
    known_urls = {s["url"] for s in state.get("scored_sources", [])}
    clean_sources = []
    for source in validated.sources:
        if source.url not in known_urls:
            logger.warning("guardrail_hallucinated_url", url=source.url)
            continue
        clean_sources.append(source)

    validated = validated.model_copy(update={"sources": clean_sources})
    return {"guardrail_passed": True, "final_report": validated.model_dump()}
