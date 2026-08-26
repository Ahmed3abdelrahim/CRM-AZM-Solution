from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel


class ChannelEnum(str, Enum):
    WEB = "web"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    CHAT = "chat"
    PORTAL = "portal"


class NormalizedAttachment(BaseModel):
    filename: str
    content_type: str
    data: bytes | None
    source_url: str | None


class NormalizedMessage(BaseModel):
    external_id: str
    channel: ChannelEnum
    from_identity: str
    to_identity: str  # the receiving identifier — matched against channel_configs.identifier
    subject: str | None
    body: str
    locale: Literal["ar", "en"]
    attachments: list[NormalizedAttachment]
    received_at: datetime


class ChannelAdapter(Protocol):
    """Plan.md §Shared Abstractions #4. `ChannelService.ingest()` is the only caller of
    `normalize()`; it is written entirely against this protocol, never against a concrete
    adapter class — adding a channel later requires zero changes to ticket creation logic."""

    channel: ClassVar[ChannelEnum]

    def normalize(self, raw: dict[str, Any]) -> NormalizedMessage: ...

    async def send_reply(self, ticket_id: UUID, body: str, locale: Literal["ar", "en"]) -> None: ...
