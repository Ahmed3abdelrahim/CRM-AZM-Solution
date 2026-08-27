from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.permissions import CurrentActor
from app.db import get_session
from app.schemas.report import AgentVolumeReport, SlaComplianceReport, TicketsByStatusReport
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])


@router.get(
    "/reports/tickets-by-status",
    response_model=TicketsByStatusReport,
    operation_id="getTicketsByStatusReport",
)
async def get_tickets_by_status_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    cross_branch: bool = Query(default=False),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = ReportService(session, actor.scope)
    return await service.tickets_by_status(actor, date_from, date_to, cross_branch)


@router.get(
    "/reports/sla-compliance", response_model=SlaComplianceReport, operation_id="getSlaComplianceReport"
)
async def get_sla_compliance_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    cross_branch: bool = Query(default=False),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = ReportService(session, actor.scope)
    return await service.sla_compliance(actor, date_from, date_to, cross_branch)


@router.get(
    "/reports/agent-volume", response_model=AgentVolumeReport, operation_id="getAgentVolumeReport"
)
async def get_agent_volume_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    cross_branch: bool = Query(default=False),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = ReportService(session, actor.scope)
    return await service.agent_volume(actor, date_from, date_to, cross_branch)
