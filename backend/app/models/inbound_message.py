import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin


class InboundMessage(Base, CreatedMixin):
    """S5 — System-nullable; see research.md Part 2. Insert-only (§0.3). data-model.md §1.25."""

    __tablename__ = "inbound_messages"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('web','email','whatsapp','sms','chat','portal')",
            name="ck_inbound_messages_channel",
        ),
        UniqueConstraint("channel", "external_id", name="uq_inbound_messages_channel_external_id"),
        Index("ix_inbound_messages_ticket_id", "ticket_id"),
    )

    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=True
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalized: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
