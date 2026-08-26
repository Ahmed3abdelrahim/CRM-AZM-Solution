import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, ReferenceLabelMixin, UpdatedMixin


class Role(Base, CreatedMixin, UpdatedMixin, ReferenceLabelMixin):
    """S6 — Global. data-model.md §1.4. No is_active/sort_order — hard DELETE."""

    __tablename__ = "roles"
    __table_args__ = (CheckConstraint("code IN ('admin','lead','agent','customer')", name="ck_roles_code"),)

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class Permission(Base, CreatedMixin, UpdatedMixin, ReferenceLabelMixin):
    """S6 — Global. data-model.md §1.5. Read-only through the API (seeded/migration-managed)."""

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class RolePermission(Base, CreatedMixin, UpdatedMixin):
    """S6 — Global. data-model.md §1.6."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )
