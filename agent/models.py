from pydantic import BaseModel, Field
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Finding(BaseModel):
    severity: Severity
    category: str  # "security" | "logic" | "test-coverage"
    file_path: str
    line_range: str | None = None
    description: str
    suggestion: str


class ReviewReport(BaseModel):
    pr_url: str
    summary: str
    findings: list[Finding]
    risk_score: float = Field(ge=0.0, le=10.0)
    model_used: str
    tokens_used: int
    cached: bool
