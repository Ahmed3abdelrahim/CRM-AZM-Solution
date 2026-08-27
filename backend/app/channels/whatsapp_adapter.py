"""Tier D stub — present and importable, never absent (PLAN.md F03 / FR-025). Registering this
adapter with `ChannelService` (T122) means `POST /channels/inbound` with `channel=whatsapp`
fails loudly with a clear reason instead of routing to the wrong channel or 404ing — adding the
real integration later requires only replacing this file's method bodies (FR-024)."""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from app.channels.base import ChannelEnum, NormalizedMessage


class WhatsappAdapter:
    channel: ClassVar[ChannelEnum] = ChannelEnum.WHATSAPP

    def normalize(self, raw: dict[str, Any]) -> NormalizedMessage:
        raise NotImplementedError(f"{self.channel} channel is Tier D — see specs/00X")

    async def send_reply(self, ticket_id: UUID, body: str, locale: str) -> None:
        raise NotImplementedError(f"{self.channel} channel is Tier D — see specs/00X")
