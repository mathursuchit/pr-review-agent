import asyncio
import json
import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth import verify_api_key
from agent.graph import build_graph

logger = structlog.get_logger()
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Build once at import time — graph is stateless
_graph = build_graph()


class ReviewRequest(BaseModel):
    pr_url: str


@router.post("/review")
@limiter.limit("10/minute")
async def review_pr(
    request: Request,
    req: ReviewRequest,
    _: str = Depends(verify_api_key),
):
    logger.info("review_requested", pr_url=req.pr_url)

    async def stream():
        initial_state: dict = {
            "pr_url": req.pr_url,
            "raw_diff": "",
            "chunks": [],
            "injection_flagged": False,
            "secrets_found": [],
            "security_findings": [],
            "logic_findings": [],
            "test_findings": [],
            "final_report": None,
            "guardrail_passed": False,
            "retry_count": 0,
            "error": None,
        }

        final_state = dict(initial_state)

        try:
            async for chunk in _graph.astream(initial_state, stream_mode="updates"):
                node_name = list(chunk.keys())[0]
                final_state.update(chunk[node_name])
                event = json.dumps({"node": node_name, "status": "complete"})
                yield f"data: {event}\n\n"
                await asyncio.sleep(0)  # yield to event loop

            result = final_state.get("final_report")
            error = final_state.get("error")
            yield f"data: {json.dumps({'result': result, 'error': error})}\n\n"
        except Exception as e:
            logger.error("stream_error", error=str(e))
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
