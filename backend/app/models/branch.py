from sqlalchemy import Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, ReferenceLabelMixin, UpdatedMixin


class Branch(Base, CreatedMixin, UpdatedMixin, ReferenceLabelMixin):
    """S6 — Global. Top of the tenancy hierarchy; data-model.md §1.1."""

    __tablename__ = "branches"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    business_hours: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
