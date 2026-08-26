from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.schemas.role import ReferenceDataBase


class Team(ReferenceDataBase):
    branch_id: UUID
    department_id: UUID


class TeamCreate(BaseModel):
    branch_id: UUID
    department_id: UUID
    label_ar: str
    label_en: str


class TeamUpdate(BaseModel):
    label_ar: str | None = None
    label_en: str | None = None


class TeamMemberCreate(BaseModel):
    user_id: UUID
