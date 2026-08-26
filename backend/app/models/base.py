import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    pass


class CreatedMixin:
    """Base columns per data-model.md §0.1 — every table.

    created_by uses use_alter=True: nearly every table's created_by references users.id, but
    users.branch_id/department_id reference branches/departments — a real FK cycle. use_alter
    defers this constraint to a post-create-all ALTER TABLE, breaking the cycle without manual
    migration ordering.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @declared_attr
    def created_by(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(
            PG_UUID(as_uuid=True),
            ForeignKey(
                "users.id",
                ondelete="SET NULL",
                use_alter=True,
                name=f"fk_{cls.__tablename__}_created_by_users",
            ),
            nullable=True,
        )


class UpdatedMixin:
    """Additional base columns per data-model.md §0.2 — every mutable table."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @declared_attr
    def updated_by(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(
            PG_UUID(as_uuid=True),
            ForeignKey(
                "users.id",
                ondelete="SET NULL",
                use_alter=True,
                name=f"fk_{cls.__tablename__}_updated_by_users",
            ),
            nullable=True,
        )


class ReferenceLabelMixin:
    """Label base per data-model.md §0.4 — reference-data tables only."""

    label_ar: Mapped[str] = mapped_column(Text, nullable=False)
    label_en: Mapped[str] = mapped_column(Text, nullable=False)
