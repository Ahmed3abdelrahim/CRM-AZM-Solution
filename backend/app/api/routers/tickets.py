from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.permissions import CurrentActor
from app.db import get_session
from app.repositories.ticket_repository import TicketFilters
from app.schemas.customer import Attachment
from app.schemas.ticket import (
    IllegalTransitionError as IllegalTransitionErrorSchema,
    Ticket,
    TicketAssign,
    TicketCreate,
    TicketEvent,
    TicketNoteCreate,
    TicketReplyCreate,
    TicketStatusChange,
    TicketSummary,
    TicketTriageCorrection,
    TicketUpdate,
)
from app.services.ticket_service import TicketService
from app.services.ticket_transition_service import TicketTransitionService

router = APIRouter(tags=["tickets"])


def _filters(
    status_id: UUID | None,
    priority_id: UUID | None,
    category_id: UUID | None,
    assignee_id: UUID | None,
    channel: str | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
) -> TicketFilters:
    return TicketFilters(
        status_id=status_id,
        priority_id=priority_id,
        category_id=category_id,
        assignee_id=assignee_id,
        channel=channel,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )


@router.get("/tickets", response_model=list[TicketSummary], operation_id="listTickets")
async def list_tickets(
    view: str | None = None,
    status_id: UUID | None = None,
    priority_id: UUID | None = None,
    category_id: UUID | None = None,
    assignee_id: UUID | None = None,
    channel: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = TicketService(session, actor.scope)
    filters = _filters(status_id, priority_id, category_id, assignee_id, channel, date_from, date_to, q)
    return await service.list(actor, view, filters, limit=limit, offset=offset)


@router.post(
    "/tickets", response_model=Ticket, status_code=status.HTTP_201_CREATED, operation_id="createTicket"
)
async def create_ticket(
    data: TicketCreate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = TicketService(session, actor.scope)
    return await service.create(actor, data)


@router.get("/tickets/{id}", response_model=Ticket, operation_id="getTicket")
async def get_ticket(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = TicketService(session, actor.scope)
    return await service.get(actor, id)


@router.patch("/tickets/{id}", response_model=Ticket, operation_id="updateTicket")
async def update_ticket(
    id: UUID,
    data: TicketUpdate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = TicketService(session, actor.scope)
    return await service.update(actor, id, data)


@router.post(
    "/tickets/{id}/status",
    response_model=Ticket,
    operation_id="changeTicketStatus",
    responses={422: {"model": IllegalTransitionErrorSchema}},
)
async def change_ticket_status(
    id: UUID,
    data: TicketStatusChange,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = TicketTransitionService(session, actor.scope)
    return await service.change_status(actor, id, data.to_status_id, data.reason)


@router.post("/tickets/{id}/assign", response_model=Ticket, operation_id="assignTicket")
async def assign_ticket(
    id: UUID,
    data: TicketAssign,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = TicketService(session, actor.scope)
    return await service.assign(actor, id, data)


@router.get("/tickets/{id}/events", response_model=list[TicketEvent], operation_id="getTicketEvents")
async def get_ticket_events(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = TicketService(session, actor.scope)
    return await service.get_events(actor, id)


@router.post(
    "/tickets/{id}/notes",
    response_model=TicketEvent,
    status_code=status.HTTP_201_CREATED,
    operation_id="addTicketNote",
)
async def add_ticket_note(
    id: UUID,
    data: TicketNoteCreate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = TicketService(session, actor.scope)
    return await service.add_note(actor, id, data.body)


@router.post(
    "/tickets/{id}/replies",
    response_model=TicketEvent,
    status_code=status.HTTP_201_CREATED,
    operation_id="addTicketReply",
)
async def add_ticket_reply(
    id: UUID,
    data: TicketReplyCreate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = TicketService(session, actor.scope)
    return await service.add_reply(actor, id, data.body)


@router.post(
    "/tickets/{id}/attachments",
    response_model=Attachment,
    status_code=status.HTTP_201_CREATED,
    operation_id="uploadTicketAttachment",
)
async def upload_ticket_attachment(
    id: UUID,
    file: UploadFile = File(...),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = TicketService(session, actor.scope)
    return await service.add_attachment(actor, id, file)


@router.post("/tickets/{id}/triage", response_model=Ticket, operation_id="correctTicketTriage")
async def correct_ticket_triage(
    id: UUID,
    data: TicketTriageCorrection,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = TicketService(session, actor.scope)
    return await service.correct_triage(actor, id, data)
