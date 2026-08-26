from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.role import ReferenceDataBase


class Category(ReferenceDataBase):
    branch_id: UUID
    department_id: UUID | None = None
    parent_id: UUID | None = None
    is_active: bool
    sort_order: int


class CategoryCreate(BaseModel):
    branch_id: UUID
    department_id: UUID | None = None
    parent_id: UUID | None = None
    label_ar: str
    label_en: str
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    label_ar: str | None = None
    label_en: str | None = None
    parent_id: UUID | None = None
    sort_order: int | None = None


class Priority(ReferenceDataBase):
    branch_id: UUID
    department_id: UUID | None = None
    code: str
    severity: int
    color: str


class PriorityCreate(BaseModel):
    branch_id: UUID
    department_id: UUID | None = None
    code: str
    label_ar: str
    label_en: str
    severity: int
    color: str


class PriorityUpdate(BaseModel):
    label_ar: str | None = None
    label_en: str | None = None
    severity: int | None = None
    color: str | None = None


class TicketStatus(ReferenceDataBase):
    branch_id: UUID
    department_id: UUID | None = None
    code: str
    is_terminal: bool
    pauses_sla: bool
    sort_order: int


class TicketStatusCreate(BaseModel):
    branch_id: UUID
    department_id: UUID | None = None
    code: str
    label_ar: str
    label_en: str
    is_terminal: bool
    pauses_sla: bool
    sort_order: int = 0


class TicketStatusUpdate(BaseModel):
    label_ar: str | None = None
    label_en: str | None = None


class StatusTransition(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    department_id: UUID | None = None
    from_status_id: UUID
    to_status_id: UUID
    required_permission: str | None = None
    requires_reason: bool


class StatusTransitionCreate(BaseModel):
    branch_id: UUID
    department_id: UUID | None = None
    from_status_id: UUID
    to_status_id: UUID
    required_permission: str | None = None
    requires_reason: bool = False


class StatusTransitionUpdate(BaseModel):
    required_permission: str | None = None
    requires_reason: bool | None = None
