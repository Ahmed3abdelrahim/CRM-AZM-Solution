import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, ReferenceLabelMixin, UpdatedMixin


class SlaPolicy(Base, CreatedMixin, UpdatedMixin, ReferenceLabelMixin):
    """S2 — Branch-scoped, dept-optional. data-model.md §1.19. No is_active/sort_order — hard DELETE."""

    __tablename__ = "sla_policies"
    __table_args__ = (
        Index(
            "ix_sla_policies_resolution_order",
            "branch_id", "department_id", "category_id", "priority_id",
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    priority_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("priorities.id", ondelete="RESTRICT"), nullable=True
    )
    first_response_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    business_hours_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
