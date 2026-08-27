from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class TicketsByStatusRow(BaseModel):
    status_id: UUID
    branch_id: UUID
    department_id: UUID
    count: int


class TicketsByStatusReport(BaseModel):
    rows: list[TicketsByStatusRow]


class SlaComplianceReport(BaseModel):
    first_response_compliance_pct: float
    resolution_compliance_pct: float


class AgentVolumeRow(BaseModel):
    agent_id: UUID
    assigned_count: int
    resolved_count: int
    avg_resolution_minutes: float


class AgentVolumeReport(BaseModel):
    rows: list[AgentVolumeRow]
