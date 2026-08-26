from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    department_id: UUID | None = None
    email: EmailStr
    full_name_ar: str
    full_name_en: str
    phone: str | None = None
    locale: str
    is_active: bool
    last_login_at: datetime | None = None


class UserCreate(BaseModel):
    branch_id: UUID
    department_id: UUID | None = None
    email: EmailStr
    password: str
    full_name_ar: str
    full_name_en: str
    phone: str | None = None
    locale: str = "ar"


class UserUpdate(BaseModel):
    full_name_ar: str | None = None
    full_name_en: str | None = None
    phone: str | None = None
    locale: str | None = None


class UserRole(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    role_id: UUID
    branch_id: UUID
    department_id: UUID


class UserRoleCreate(BaseModel):
    role_id: UUID
    branch_id: UUID
    department_id: UUID
