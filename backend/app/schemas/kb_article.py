from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class KbArticle(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    department_id: UUID | None = None
    slug: str
    title_ar: str
    title_en: str
    body_ar: str
    body_en: str
    category_id: UUID
    is_published: bool
    view_count: int
    helpful_count: int


class KbArticleCreate(BaseModel):
    branch_id: UUID
    department_id: UUID | None = None
    slug: str
    title_ar: str
    title_en: str
    body_ar: str
    body_en: str
    category_id: UUID


class KbArticleUpdate(BaseModel):
    title_ar: str | None = None
    title_en: str | None = None
    body_ar: str | None = None
    body_en: str | None = None
    category_id: UUID | None = None


class KbSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    article: KbArticle
    score: float
    matched_locale: Literal["ar", "en"] | None = None
