from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Customer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    department_id: UUID
    customer_type: str
    full_name_ar: str
    full_name_en: str | None = None
    national_id: str | None = None
    organization_name: str | None = None
    preferred_locale: str
    notes: str | None = None
    is_active: bool


class ContactMethodCreate(BaseModel):
    kind: str
    value: str
    is_primary: bool


class CustomerCreate(BaseModel):
    branch_id: UUID
    department_id: UUID
    customer_type: str
    full_name_ar: str
    full_name_en: str | None = None
    national_id: str | None = None
    organization_name: str | None = None
    preferred_locale: str
    notes: str | None = None
    contact_methods: list[ContactMethodCreate] = Field(min_length=1)


class CustomerUpdate(BaseModel):
    full_name_ar: str | None = None
    full_name_en: str | None = None
    organization_name: str | None = None
    preferred_locale: str | None = None
    notes: str | None = None


class ContactMethod(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    kind: str
    value: str
    is_primary: bool
    is_verified: bool


class AttachmentUpload(BaseModel):
    """contracts/openapi.yaml's multipart marker schema — FastAPI parses the actual upload via
    an `UploadFile` route parameter (app/api/routers/customers.py), not by validating this model
    directly, since Pydantic doesn't model `multipart/form-data` file parts."""

    file: bytes


class Attachment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID | None = None
    customer_id: UUID | None = None
    filename: str
    content_type: str
    size_bytes: int
    storage_key: str


class TicketSummary(BaseModel):
    """Mirrors contracts/openapi.yaml's global `TicketSummary` component — needed here only to
    type `CustomerHistory.tickets` (FR-014). Batch 4d's `schemas/ticket.py` (T071) owns the
    canonical copy used by the rest of the ticket API surface; this batch does not touch tickets
    beyond reading them for a customer's history."""

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


class TicketEvent(BaseModel):
    """Mirrors contracts/openapi.yaml's global `TicketEvent` component — see `TicketSummary`
    above for why a copy lives here rather than an import from a batch-4d file that doesn't
    exist yet."""

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


class CustomerHistory(BaseModel):
    tickets: list[TicketSummary]
    events: list[TicketEvent]
