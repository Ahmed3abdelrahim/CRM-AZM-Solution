from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.schemas.role import ReferenceDataBase


class QuickReply(ReferenceDataBase):
    branch_id: UUID
    department_id: UUID
    category_id: UUID | None = None
    body_ar: str
    body_en: str


class QuickReplyCreate(BaseModel):
    branch_id: UUID
    department_id: UUID
    category_id: UUID | None = None
    label_ar: str
    label_en: str
    body_ar: str
    body_en: str


class QuickReplyUpdate(BaseModel):
    label_ar: str | None = None
    label_en: str | None = None
    body_ar: str | None = None
    body_en: str | None = None
