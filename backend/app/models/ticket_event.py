import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin

_EVENT_TYPES = (
    "created", "status_changed", "assigned", "reassigned", "field_changed", "note_added",
    "reply_sent", "attachment_added", "sla_breached", "reopened", "ai_suggestion_applied",
)


class TicketEvent(Base, CreatedMixin):
    """S4 — Transitive, via tickets. Insert-only (§0.3). data-model.md §1.17."""

    __tablename__ = "ticket_events"
    __table_args__ = (
        CheckConstraint(f"event_type IN {_EVENT_TYPES}", name="ck_ticket_events_event_type"),
        CheckConstraint("visibility IN ('internal','customer')", name="ck_ticket_events_visibility"),
        Index("ix_ticket_events_ticket_created", "ticket_id", "created_at"),
        Index("ix_ticket_events_correlation_id", "correlation_id"),
    )

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    field_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
