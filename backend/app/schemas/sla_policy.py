from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.schemas.role import ReferenceDataBase


class SlaPolicy(ReferenceDataBase):
    branch_id: UUID
    department_id: UUID | None = None
    category_id: UUID | None = None
    priority_id: UUID | None = None
    first_response_minutes: int
    resolution_minutes: int
    business_hours_only: bool


class SlaPolicyCreate(BaseModel):
    branch_id: UUID
    department_id: UUID | None = None
    category_id: UUID | None = None
    priority_id: UUID | None = None
    label_ar: str
    label_en: str
    first_response_minutes: int
    resolution_minutes: int
    business_hours_only: bool = False


class SlaPolicyUpdate(BaseModel):
    label_ar: str | None = None
    label_en: str | None = None
    first_response_minutes: int | None = None
    resolution_minutes: int | None = None
    business_hours_only: bool | None = None
