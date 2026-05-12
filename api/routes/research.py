import asyncio
import json
import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth import verify_api_key
from agent.graph import build_graph

logger = structlog.get_logger()
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_graph = build_graph()

NODE_LABELS = {
    "search":          "Searching the web",
    "read_pages":      "Reading pages",
    "score_relevance": "Scoring source relevance",
    "decide_next":     "Deciding next step",
    "synthesize":      "Synthesizing report",
    "post_guardrails": "Validating citations",
}


class ResearchRequest(BaseModel):
    question: str
    max_depth: int = Field(default=2, ge=1, le=3)


@router.post("/research")
@limiter.limit("10/minute")
async def research(
    request: Request,
    req: ResearchRequest,
    _: str = Depends(verify_api_key),
):
    logger.info("research_requested", question=req.question[:100])

    async def stream():
        initial: dict = {
            "question": req.question,
            "search_queries": [],
            "search_results": [],
            "pages_read": [],
            "scored_sources": [],
            "depth": 0,
            "max_depth": req.max_depth,
            "token_budget": 50_000,
            "tokens_used": 0,
            "should_continue": True,
            "final_report": None,
            "guardrail_passed": False,
            "retry_count": 0,
            "error": None,
        }

        final_state = dict(initial)

        try:
            async for chunk in _graph.astream(initial, stream_mode="updates"):
                node = list(chunk.keys())[0]
                final_state.update(chunk[node])
                label = NODE_LABELS.get(node, node)
                yield f"data: {json.dumps({'node': node, 'label': label, 'status': 'complete'})}\n\n"
                await asyncio.sleep(0)

            yield f"data: {json.dumps({'result': final_state.get('final_report'), 'error': final_state.get('error')})}\n\n"
        except Exception as e:
            logger.error("stream_error", error=str(e))
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
