from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class AiSummaryResponse(BaseModel):
    summary: str
    fallback_used: bool


class AiSuggestedReplyResponse(BaseModel):
    draft: str
    fallback_used: bool


class CategorizationDecision(BaseModel):
    accepted: bool
    override_category_id: UUID | None = None


class BenchmarkResult(BaseModel):
    scored_count: int
    accuracy: float
