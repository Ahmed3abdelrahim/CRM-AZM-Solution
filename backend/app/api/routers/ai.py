from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.permissions import CurrentActor
from app.db import get_session
from app.schemas.ai import (
    AiSuggestedReplyResponse,
    AiSummaryResponse,
    BenchmarkResult,
    CategorizationDecision,
)
from app.schemas.ticket import Ticket
from app.services.ai_service import AiService

router = APIRouter(tags=["ai"])


@router.post("/tickets/{id}/ai/summary", response_model=AiSummaryResponse, operation_id="getAiSummary")
async def get_ai_summary(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = AiService(session, actor.scope)
    return await service.summarize(actor, id)


@router.post(
    "/tickets/{id}/ai/suggested-reply",
    response_model=AiSuggestedReplyResponse,
    operation_id="getAiSuggestedReply",
)
async def get_ai_suggested_reply(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = AiService(session, actor.scope)
    return await service.suggest_reply(actor, id)


@router.get("/tickets/{id}/ai/suggested-solution", operation_id="getAiSuggestedSolution")
async def get_ai_suggested_solution(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = AiService(session, actor.scope)
    return await service.suggest_solution(actor, id)


@router.post(
    "/tickets/{id}/ai/categorization-suggestion",
    response_model=Ticket,
    operation_id="acceptAiCategorization",
)
async def accept_ai_categorization(
    id: UUID,
    data: CategorizationDecision,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = AiService(session, actor.scope)
    return await service.apply_categorization_decision(actor, id, data.accepted, data.override_category_id)


@router.post(
    "/ai/categorization-benchmark",
    response_model=BenchmarkResult,
    operation_id="runCategorizationBenchmark",
)
async def run_categorization_benchmark(
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = AiService(session, actor.scope)
    return await service.run_categorization_benchmark(actor)
