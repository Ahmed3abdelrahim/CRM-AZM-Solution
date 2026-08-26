from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

BreachState = Literal["on_track", "at_risk", "breached"]


class TicketSummary(BaseModel):
    """The canonical copy used by the rest of the ticket API surface (contracts/openapi.yaml's
    `TicketSummary`) — `app/schemas/customer.py` keeps its own pre-existing copy solely to type
    `CustomerHistory.tickets` (F01, batch 4c), predating this file."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference_no: str
    subject: str
    status_id: UUID
    priority_id: UUID
    category_id: UUID
    assignee_id: UUID | None = None
    team_id: UUID | None = None
    channel: str
    source_locale: str
    needs_triage: bool
    created_at: datetime


class Ticket(TicketSummary):
    branch_id: UUID
    department_id: UUID
    customer_id: UUID
    description: str
    sla_policy_id: UUID | None = None
    first_response_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    reopened_count: int
    sla_paused_ms: int
    ai_suggested_category_id: UUID | None = None
    ai_category_confidence: float | None = None
    sla_first_response_due_at: datetime | None = None
    sla_resolution_due_at: datetime | None = None
    sla_breach_state: BreachState | None = None


class TicketCreate(BaseModel):
    branch_id: UUID
    department_id: UUID
    customer_id: UUID
    subject: str
    description: str
    category_id: UUID
    priority_id: UUID
    channel: str
    source_locale: str
    team_id: UUID | None = None


class TicketUpdate(BaseModel):
    subject: str | None = None
    description: str | None = None
    category_id: UUID | None = None
    priority_id: UUID | None = None


class TicketStatusChange(BaseModel):
    to_status_id: UUID
    reason: str | None = None


class TicketAssign(BaseModel):
    assignee_id: UUID | None = None
    team_id: UUID | None = None


class SlaOverrideRequest(BaseModel):
    sla_policy_id: UUID
    reason: str = Field(min_length=1)


class TicketTriageCorrection(BaseModel):
    branch_id: UUID
    department_id: UUID


class TicketNoteCreate(BaseModel):
    body: str


class TicketReplyCreate(BaseModel):
    body: str


class TicketEvent(BaseModel):
    """The canonical copy used by the rest of the ticket API surface — see `TicketSummary` above
    for why `app/schemas/customer.py` keeps its own pre-existing copy too."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    actor_id: UUID | None = None
    event_type: str
    field_name: str | None = None
    old_value: Any = None
    new_value: Any = None
    body: str | None = None
    visibility: str
    reason: str | None = None
    correlation_id: UUID
    created_at: datetime


class IllegalTransitionError(BaseModel):
    """Mirrors contracts/openapi.yaml's `IllegalTransitionError` — documents the 422 response
    shape for OpenAPI generation; the actual response is built by
    `app/core/errors.py::illegal_transition_handler`, which bypasses `response_model` validation
    the same way every other error response in this codebase does (no `ErrorResponse` Pydantic
    schema exists either)."""

    message_ar: str
    message_en: str
    current_status_id: UUID
    permitted_status_ids: list[UUID]
