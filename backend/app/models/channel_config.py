import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, UpdatedMixin


class ChannelConfig(Base, CreatedMixin, UpdatedMixin):
    """S1 — Fully scoped. data-model.md §1.26."""

    __tablename__ = "channel_configs"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('web','email','whatsapp','sms','chat','portal')",
            name="ck_channel_configs_channel",
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    identifier: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    default_category_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
