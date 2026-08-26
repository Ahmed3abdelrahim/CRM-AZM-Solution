from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReferenceDataBase(BaseModel):
    """contracts/openapi.yaml `ReferenceDataBase` — only label_ar/label_en are universal;
    is_active/sort_order are added per-schema below only where data-model.md §0.4 says so."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label_ar: str
    label_en: str


class Branch(ReferenceDataBase):
    code: str
    timezone: str
    business_hours: dict[str, Any]
    is_active: bool


class BranchCreate(BaseModel):
    code: str
    label_ar: str
    label_en: str
    timezone: str
    business_hours: dict[str, Any]


class BranchUpdate(BaseModel):
    label_ar: str | None = None
    label_en: str | None = None
    timezone: str | None = None
    business_hours: dict[str, Any] | None = None


class Department(ReferenceDataBase):
    branch_id: UUID
    code: str
    is_active: bool


class DepartmentCreate(BaseModel):
    branch_id: UUID
    code: str
    label_ar: str
    label_en: str


class DepartmentUpdate(BaseModel):
    label_ar: str | None = None
    label_en: str | None = None


class Role(ReferenceDataBase):
    code: str


class RoleCreate(BaseModel):
    code: str
    label_ar: str
    label_en: str


class RoleUpdate(BaseModel):
    label_ar: str | None = None
    label_en: str | None = None


class Permission(ReferenceDataBase):
    code: str
