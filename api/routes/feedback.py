import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from feedback.store import save_feedback

logger = structlog.get_logger()
router = APIRouter()


class FeedbackRequest(BaseModel):
    pr_url: str
    finding_id: str  # "{category}:{file_path}:{line_range}" or a hash
    correct: bool
    comment: str | None = None


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    save_feedback(req.model_dump())
    logger.info("feedback_received", pr_url=req.pr_url, correct=req.correct)
    return {"status": "received"}
