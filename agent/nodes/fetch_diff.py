import structlog
from agent.state import ReviewState
from agent.tools.github import parse_pr_url, fetch_diff as _fetch_diff

logger = structlog.get_logger()

MAX_DIFF_CHARS = 30_000  # ~8k tokens


async def run(state: ReviewState) -> dict:
    pr_url = state["pr_url"]
    try:
        owner, repo, pr_number = parse_pr_url(pr_url)
        diff = await _fetch_diff(owner, repo, pr_number)
        if len(diff) > MAX_DIFF_CHARS:
            chunks = [diff[i : i + MAX_DIFF_CHARS] for i in range(0, len(diff), MAX_DIFF_CHARS)]
            logger.info("diff_chunked", chunks=len(chunks), pr_url=pr_url)
        else:
            chunks = [diff]
        return {"raw_diff": diff[:MAX_DIFF_CHARS], "chunks": chunks, "error": None}
    except Exception as e:
        logger.error("fetch_diff_failed", error=str(e), pr_url=pr_url)
        return {"raw_diff": "", "chunks": [], "error": str(e)}
