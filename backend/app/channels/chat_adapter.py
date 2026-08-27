"""Tier D stub — see whatsapp_adapter.py's module docstring for the rationale."""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from app.channels.base import ChannelEnum, NormalizedMessage


class ChatAdapter:
    channel: ClassVar[ChannelEnum] = ChannelEnum.CHAT

    def normalize(self, raw: dict[str, Any]) -> NormalizedMessage:
        raise NotImplementedError(f"{self.channel} channel is Tier D — see specs/00X")

    async def send_reply(self, ticket_id: UUID, body: str, locale: str) -> None:
        raise NotImplementedError(f"{self.channel} channel is Tier D — see specs/00X")
