import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, UpdatedMixin


class Customer(Base, CreatedMixin, UpdatedMixin):
    """S1 — Fully scoped. data-model.md §1.10. Never hard-deleted (FR-013)."""

    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "customer_type IN ('individual','organization')", name="ck_customers_customer_type"
        ),
        CheckConstraint("preferred_locale IN ('ar','en')", name="ck_customers_preferred_locale"),
        Index("ix_customers_branch_dept_active", "branch_id", "department_id", "is_active"),
        Index(
            "ix_customers_full_name_ar_trgm", "full_name_ar", postgresql_using="gin",
            postgresql_ops={"full_name_ar": "gin_trgm_ops"},
        ),
        Index(
            "ix_customers_full_name_en_trgm", "full_name_en", postgresql_using="gin",
            postgresql_ops={"full_name_en": "gin_trgm_ops"},
        ),
        Index(
            "ix_customers_organization_name_trgm", "organization_name", postgresql_using="gin",
            postgresql_ops={"organization_name": "gin_trgm_ops"},
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    customer_type: Mapped[str] = mapped_column(Text, nullable=False)
    full_name_ar: Mapped[str] = mapped_column(Text, nullable=False)
    full_name_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    national_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    organization_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_locale: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class ContactMethod(Base, CreatedMixin, UpdatedMixin):
    """S4 — Transitive, via customers. data-model.md §1.11."""

    __tablename__ = "contact_methods"
    __table_args__ = (
        CheckConstraint("kind IN ('phone','email','whatsapp','other')", name="ck_contact_methods_kind"),
        Index(
            "ix_contact_methods_value_trgm", "value", postgresql_using="gin",
            postgresql_ops={"value": "gin_trgm_ops"},
        ),
        Index(
            "uq_contact_methods_primary_per_customer", "customer_id", unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
