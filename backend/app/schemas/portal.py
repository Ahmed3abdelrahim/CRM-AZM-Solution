from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.ticket import TicketEvent


class PortalTicketSubmit(BaseModel):
    full_name: str
    contact_kind: Literal["phone", "email", "whatsapp", "other"]
    contact_value: str
    subject: str
    description: str
    category_id: UUID


class PortalTicketReceipt(BaseModel):
    reference_no: str


class PortalTicketView(BaseModel):
    reference_no: str
    subject: str
    status_id: UUID
    created_at: datetime
    events: list[TicketEvent] = []
