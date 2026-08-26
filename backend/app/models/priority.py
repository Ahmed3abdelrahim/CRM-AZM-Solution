import uuid

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, ReferenceLabelMixin, UpdatedMixin


class Priority(Base, CreatedMixin, UpdatedMixin, ReferenceLabelMixin):
    """S2 — Branch-scoped, dept-optional. data-model.md §1.13. No is_active/sort_order — hard DELETE."""

    __tablename__ = "priorities"
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "department_id", "code", name="uq_priorities_branch_dept_code"
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(Text, nullable=False)
