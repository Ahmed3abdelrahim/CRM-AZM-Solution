import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, ReferenceLabelMixin, UpdatedMixin


class TicketStatus(Base, CreatedMixin, UpdatedMixin, ReferenceLabelMixin):
    """S2 — Branch-scoped, dept-optional. data-model.md §1.14. code is plain TEXT, no CHECK — §0.5."""

    __tablename__ = "ticket_statuses"
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "department_id", "code", name="uq_ticket_statuses_branch_dept_code"
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pauses_sla: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
