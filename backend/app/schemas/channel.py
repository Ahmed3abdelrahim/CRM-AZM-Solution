from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NormalizedMessagePayload(BaseModel):
    external_id: str
    channel: Literal["web", "email", "whatsapp", "sms", "chat", "portal"]
    from_identity: str
    to_identity: str
    subject: str | None = None
    body: str
    locale: Literal["ar", "en"]


class InboundMessageAccepted(BaseModel):
    inbound_message_id: UUID
    ticket_id: UUID | None = None


class ApiKey(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID | None = None
    label: str
    scopes: list[str]
    last_used_at: datetime | None = None
    expires_at: datetime | None = None


class ApiKeyCreate(BaseModel):
    branch_id: UUID | None = None
    label: str
    scopes: list[str]
    expires_at: datetime | None = None


class ApiKeyCreated(ApiKey):
    plaintext_key: str
