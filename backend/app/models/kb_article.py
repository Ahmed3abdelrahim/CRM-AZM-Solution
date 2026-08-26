import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, UpdatedMixin


class KbArticle(Base, CreatedMixin, UpdatedMixin):
    """S2 — see research.md Part 2. data-model.md §1.21."""

    __tablename__ = "kb_articles"
    __table_args__ = (
        UniqueConstraint("branch_id", "slug", name="uq_kb_articles_branch_slug"),
        Index(
            "ix_kb_articles_body_ar_trgm", "body_ar", postgresql_using="gin",
            postgresql_ops={"body_ar": "gin_trgm_ops"},
        ),
        Index(
            "ix_kb_articles_body_en_trgm", "body_en", postgresql_using="gin",
            postgresql_ops={"body_en": "gin_trgm_ops"},
        ),
        Index("ix_kb_articles_category_id", "category_id"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    title_ar: Mapped[str] = mapped_column(Text, nullable=False)
    title_en: Mapped[str] = mapped_column(Text, nullable=False)
    body_ar: Mapped[str] = mapped_column(Text, nullable=False)
    body_en: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    helpful_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class KbArticleChunk(Base, CreatedMixin, UpdatedMixin):
    """S4 — Transitive, via kb_articles; see research.md Part 2. data-model.md §1.22."""

    __tablename__ = "kb_article_chunks"
    __table_args__ = (
        CheckConstraint("locale IN ('ar','en')", name="ck_kb_article_chunks_locale"),
        UniqueConstraint(
            "kb_article_id", "locale", "chunk_index", name="uq_kb_article_chunks_article_locale_index"
        ),
        Index(
            "ix_kb_article_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_kb_article_chunks_content_trgm", "content", postgresql_using="gin",
            postgresql_ops={"content": "gin_trgm_ops"},
        ),
    )

    kb_article_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("kb_articles.id", ondelete="CASCADE"), nullable=False
    )
    locale: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
