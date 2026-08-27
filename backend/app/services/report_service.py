from __future__ import annotations

from datetime import date

from sqlalchemy import and_, func, literal, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import CurrentActor, PermissionDeniedError, require_permission
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.repositories.scoped_repository import TenantScope
from app.schemas.report import (
    AgentVolumeReport,
    AgentVolumeRow,
    SlaComplianceReport,
    TicketsByStatusReport,
    TicketsByStatusRow,
)


class ReportService:
    """plan.md §Service Classes — `ReportService`. All three methods: if `cross_branch=True` is
    requested, raise `PermissionDeniedError("report.cross_branch")` unless that code is in
    `actor.permissions`; only then does the constructed `TenantScope` set `cross_branch=True`
    before querying (FR-060)."""

    def __init__(self, session: AsyncSession, scope: TenantScope) -> None:
        self.session = session
        self.scope = scope

    def _resolve_scope(self, actor: CurrentActor, cross_branch: bool) -> TenantScope:
        if not cross_branch:
            return self.scope
        if "report.cross_branch" not in actor.permissions:
            raise PermissionDeniedError("report.cross_branch")
        return TenantScope(branch_id=self.scope.branch_id, department_id=self.scope.department_id, cross_branch=True)

    def _scope_filter(self, scope: TenantScope):
        if scope.cross_branch:
            return true()
        return and_(Ticket.branch_id == scope.branch_id, Ticket.department_id == scope.department_id)

    def _date_filter(self, date_from: date | None, date_to: date | None):
        clauses = []
        if date_from is not None:
            clauses.append(Ticket.created_at >= date_from)
        if date_to is not None:
            clauses.append(Ticket.created_at <= date_to)
        return clauses

    @require_permission("ticket.read")
    async def tickets_by_status(
        self,
        actor: CurrentActor,
        date_from: date | None,
        date_to: date | None,
        cross_branch: bool,
    ) -> TicketsByStatusReport:
        scope = self._resolve_scope(actor, cross_branch)
        stmt = (
            select(Ticket.status_id, Ticket.branch_id, Ticket.department_id, func.count(Ticket.id))
            .where(self._scope_filter(scope), *self._date_filter(date_from, date_to))
            .group_by(Ticket.status_id, Ticket.branch_id, Ticket.department_id)
        )
        result = await self.session.execute(stmt)
        rows = [
            TicketsByStatusRow(status_id=status_id, branch_id=branch_id, department_id=department_id, count=count)
            for status_id, branch_id, department_id, count in result.all()
        ]
        return TicketsByStatusReport(rows=rows)

    @require_permission("ticket.read")
    async def sla_compliance(
        self,
        actor: CurrentActor,
        date_from: date | None,
        date_to: date | None,
        cross_branch: bool,
    ) -> SlaComplianceReport:
        """FR-059 — tracked separately for first response and resolution. Compliance for a target
        is the share of SLA-applicable tickets (`sla_policy_id IS NOT NULL`) with no stored
        `sla_breached` event for that target (`field_name`, `app/services/sla_service.py
        sweep_breaches` — the one place that event is ever written), matching Principle XII: a
        report reads only stored data, never re-derives breach state from live business-hours
        arithmetic across a whole ticket set."""
        scope = self._resolve_scope(actor, cross_branch)
        base_filter = and_(
            self._scope_filter(scope),
            Ticket.sla_policy_id.isnot(None),
            *self._date_filter(date_from, date_to),
        )

        applicable_result = await self.session.execute(select(func.count(Ticket.id)).where(base_filter))
        applicable_count = applicable_result.scalar_one()
        if applicable_count == 0:
            return SlaComplianceReport(first_response_compliance_pct=0.0, resolution_compliance_pct=0.0)

        pct_by_target: dict[str, float] = {}
        for target in ("first_response", "resolution"):
            breached_stmt = (
                select(func.count(func.distinct(Ticket.id)))
                .select_from(Ticket)
                .join(
                    TicketEvent,
                    and_(
                        TicketEvent.ticket_id == Ticket.id,
                        TicketEvent.event_type == "sla_breached",
                        TicketEvent.field_name == target,
                    ),
                )
                .where(base_filter)
            )
            breached_result = await self.session.execute(breached_stmt)
            breached_count = breached_result.scalar_one()
            pct_by_target[target] = round((applicable_count - breached_count) / applicable_count * 100, 2)

        return SlaComplianceReport(
            first_response_compliance_pct=pct_by_target["first_response"],
            resolution_compliance_pct=pct_by_target["resolution"],
        )

    @require_permission("ticket.read")
    async def agent_volume(
        self,
        actor: CurrentActor,
        date_from: date | None,
        date_to: date | None,
        cross_branch: bool,
    ) -> AgentVolumeReport:
        scope = self._resolve_scope(actor, cross_branch)
        resolution_minutes = func.extract("epoch", Ticket.resolved_at - Ticket.created_at) / 60
        stmt = (
            select(
                Ticket.assignee_id,
                func.count(Ticket.id),
                func.count(Ticket.resolved_at),
                func.coalesce(func.avg(resolution_minutes), literal(0.0)),
            )
            .where(
                self._scope_filter(scope),
                Ticket.assignee_id.isnot(None),
                *self._date_filter(date_from, date_to),
            )
            .group_by(Ticket.assignee_id)
        )
        result = await self.session.execute(stmt)
        rows = [
            AgentVolumeRow(
                agent_id=agent_id,
                assigned_count=assigned_count,
                resolved_count=resolved_count,
                avg_resolution_minutes=round(float(avg_minutes), 2),
            )
            for agent_id, assigned_count, resolved_count, avg_minutes in result.all()
        ]
        return AgentVolumeReport(rows=rows)
