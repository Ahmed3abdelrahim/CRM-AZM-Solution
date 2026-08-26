import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin


class LlmCall(Base, CreatedMixin):
    """S5 — per PLAN.md §4.1. Insert-only (§0.3). data-model.md §1.27."""

    __tablename__ = "llm_calls"
    __table_args__ = (
        CheckConstraint(
            "capability IN ('categorize','summarize','suggest_reply','suggest_solution')",
            name="ck_llm_calls_capability",
        ),
        Index("ix_llm_calls_ticket_created", "ticket_id", "created_at"),
        Index("ix_llm_calls_capability_created", "capability", "created_at"),
    )

    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=True
    )
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )
    capability: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
