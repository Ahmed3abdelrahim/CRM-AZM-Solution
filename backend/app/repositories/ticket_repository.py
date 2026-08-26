from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_

from app.models.sla_policy import SlaPolicy
from app.models.ticket import Ticket
from app.models.ticket_status import TicketStatus
from app.repositories.scoped_repository import ScopedRepository, ScopingMode


@dataclass(frozen=True)
class TicketFilters:
    """The shared filter set (FR-026) every F04 dashboard view and `TicketService.list` apply on
    top of their own view-specific predicate."""

    status_id: UUID | None = None
    priority_id: UUID | None = None
    category_id: UUID | None = None
    assignee_id: UUID | None = None
    channel: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    q: str | None = None


class TicketRepository(ScopedRepository[Ticket]):
    """`ScopedRepository[Ticket]` (S1) plus the five F04 dashboard-view query builders and the
    shared filter set — used by both `TicketService.list` (this batch) and Batch 4e's dashboard.
    Never overrides `_scoped_select`; every view/filter method below starts from it."""

    model = Ticket
    scoping_mode = ScopingMode.S1_FULL

    def _apply_filters(self, stmt: Select[Any], filters: TicketFilters | None) -> Select[Any]:
        if filters is None:
            return stmt
        if filters.status_id is not None:
            stmt = stmt.where(Ticket.status_id == filters.status_id)
        if filters.priority_id is not None:
            stmt = stmt.where(Ticket.priority_id == filters.priority_id)
        if filters.category_id is not None:
            stmt = stmt.where(Ticket.category_id == filters.category_id)
        if filters.assignee_id is not None:
            stmt = stmt.where(Ticket.assignee_id == filters.assignee_id)
        if filters.channel is not None:
            stmt = stmt.where(Ticket.channel == filters.channel)
        if filters.date_from is not None:
            stmt = stmt.where(Ticket.created_at >= filters.date_from)
        if filters.date_to is not None:
            stmt = stmt.where(Ticket.created_at <= filters.date_to)
        if filters.q:
            pattern = f"%{filters.q}%"
            stmt = stmt.where(or_(Ticket.subject.ilike(pattern), Ticket.reference_no.ilike(pattern)))
        return stmt

    async def _execute(self, stmt: Select[Any], limit: int, offset: int) -> list[Ticket]:
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_filtered(
        self, filters: TicketFilters | None = None, limit: int = 50, offset: int = 0
    ) -> list[Ticket]:
        stmt = self._apply_filters(self._scoped_select(), filters).order_by(Ticket.created_at.desc())
        return await self._execute(stmt, limit, offset)

    async def my_open(
        self, assignee_id: UUID, filters: TicketFilters | None = None, limit: int = 50, offset: int = 0
    ) -> list[Ticket]:
        stmt = (
            self._scoped_select()
            .join(TicketStatus, Ticket.status_id == TicketStatus.id)
            .where(Ticket.assignee_id == assignee_id, TicketStatus.is_terminal.is_(False))
        )
        stmt = self._apply_filters(stmt, filters).order_by(Ticket.created_at.desc())
        return await self._execute(stmt, limit, offset)

    async def team_queue(
        self, team_id: UUID, filters: TicketFilters | None = None, limit: int = 50, offset: int = 0
    ) -> list[Ticket]:
        stmt = (
            self._scoped_select()
            .join(TicketStatus, Ticket.status_id == TicketStatus.id)
            .where(Ticket.team_id == team_id, TicketStatus.is_terminal.is_(False))
        )
        stmt = self._apply_filters(stmt, filters).order_by(Ticket.created_at.desc())
        return await self._execute(stmt, limit, offset)

    async def unassigned(
        self, filters: TicketFilters | None = None, limit: int = 50, offset: int = 0
    ) -> list[Ticket]:
        """Includes `needs_triage` tickets — they are also unassigned by construction
        (FR-023a) — no separate predicate is needed to surface them here."""
        stmt = self._scoped_select().where(Ticket.assignee_id.is_(None))
        stmt = self._apply_filters(stmt, filters).order_by(Ticket.created_at.asc())
        return await self._execute(stmt, limit, offset)

    async def breaching_soon(
        self, filters: TicketFilters | None = None, limit: int = 50, offset: int = 0
    ) -> list[Ticket]:
        """Orders open tickets by remaining time to resolution breach, ascending. This is a
        repository-level approximation (`created_at + sla_policies.resolution_minutes`, ignoring
        `sla_paused_ms` and business hours) so the view is queryable before Batch 4f's
        `SlaService.compute_due_dates`/`compute_breach_state` (the real, pure-function
        computation this repository does not attempt to duplicate) exist."""
        due_at = Ticket.created_at + func.make_interval(0, 0, 0, 0, 0, SlaPolicy.resolution_minutes)
        remaining_seconds = func.extract("epoch", due_at - func.now())
        stmt = (
            self._scoped_select()
            .join(SlaPolicy, Ticket.sla_policy_id == SlaPolicy.id)
            .join(TicketStatus, Ticket.status_id == TicketStatus.id)
            .where(TicketStatus.is_terminal.is_(False))
        )
        stmt = self._apply_filters(stmt, filters).order_by(remaining_seconds.asc())
        return await self._execute(stmt, limit, offset)

    async def recently_closed(
        self, filters: TicketFilters | None = None, limit: int = 50, offset: int = 0
    ) -> list[Ticket]:
        stmt = (
            self._scoped_select()
            .join(TicketStatus, Ticket.status_id == TicketStatus.id)
            .where(TicketStatus.is_terminal.is_(True))
        )
        stmt = self._apply_filters(stmt, filters).order_by(Ticket.updated_at.desc())
        return await self._execute(stmt, limit, offset)
