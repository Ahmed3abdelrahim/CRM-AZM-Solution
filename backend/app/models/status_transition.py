import uuid

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, UpdatedMixin


class StatusTransition(Base, CreatedMixin, UpdatedMixin):
    """S2 — the workflow engine (Principle XI). data-model.md §1.15. No label fields."""

    __tablename__ = "status_transitions"
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "department_id", "from_status_id", "to_status_id",
            name="uq_status_transitions_scope_from_to",
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    from_status_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ticket_statuses.id", ondelete="RESTRICT"), nullable=False
    )
    to_status_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ticket_statuses.id", ondelete="RESTRICT"), nullable=False
    )
    required_permission: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_reason: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
