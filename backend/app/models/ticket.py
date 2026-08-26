import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, UpdatedMixin


class Ticket(Base, CreatedMixin, UpdatedMixin):
    """S1 — Fully scoped. data-model.md §1.16."""

    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('web','email','whatsapp','sms','chat','portal')", name="ck_tickets_channel"
        ),
        CheckConstraint("source_locale IN ('ar','en')", name="ck_tickets_source_locale"),
        Index("ix_tickets_branch_dept_status", "branch_id", "department_id", "status_id"),
        Index("ix_tickets_assignee_status", "assignee_id", "status_id"),
        Index("ix_tickets_team_status", "team_id", "status_id"),
        Index(
            "ix_tickets_unassigned_queue", "department_id", "status_id",
            postgresql_where=text("assignee_id IS NULL"),
        ),
        Index("ix_tickets_created_at", "created_at"),
        Index("ix_tickets_needs_triage", "status_id", postgresql_where=text("needs_triage")),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    reference_no: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    priority_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("priorities.id", ondelete="RESTRICT"), nullable=False
    )
    status_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ticket_statuses.id", ondelete="RESTRICT"), nullable=False
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    source_locale: Mapped[str] = mapped_column(Text, nullable=False)
    sla_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("sla_policies.id", ondelete="RESTRICT"), nullable=True
    )
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sla_paused_ms: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    needs_triage: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    ai_suggested_category_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    ai_category_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    # RESERVED, Tier D (specs/005-csat-feedback) — no CHECK range constraint yet, nothing writes it.
    csat_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    csat_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
