from pydantic import BaseModel, Field


class Source(BaseModel):
    url: str
    title: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    trust_score: float = Field(ge=0.0, le=1.0)
    excerpt: str


class ResearchReport(BaseModel):
    question: str
    summary: str
    key_findings: list[str]
    sources: list[Source]
    confidence_score: float = Field(ge=0.0, le=1.0)
    depth_reached: int
    tokens_used: int
    cached: bool
