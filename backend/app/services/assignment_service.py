from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Permission, RolePermission
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.user import User
from app.models.user_role import UserRole


class AssignmentService:
    """plan.md §Service Classes — `AssignmentService`. Called only by `categorization_job`,
    after categorization completes — never directly by `TicketService.create` (`TicketCreate`
    never accepts `assignee_id`, and a second, synchronous call site there would risk
    double-assigning a ticket against the async job's own call, per plan.md's own note)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _eligible_agents(self, branch_id: UUID, department_id: UUID) -> list[UUID]:
        """Active users holding `ticket.own` in the ticket's own branch/department, ordered
        deterministically (by `id`) so rotation below is stable across runs."""

        stmt = (
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(RolePermission, RolePermission.role_id == UserRole.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                Permission.code == "ticket.own",
                UserRole.branch_id == branch_id,
                UserRole.department_id == department_id,
                User.is_active.is_(True),
            )
            .distinct()
            .order_by(User.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _next_in_rotation(self, branch_id: UUID, department_id: UUID, eligible: list[UUID]) -> UUID:
        """Stateless round-robin (no separate "last assigned" column anywhere in the schema,
        matching this codebase's stateless-derivation style elsewhere, e.g. `SlaService`):
        the eligible agent after whoever was assigned the most recently updated ticket in this
        department, wrapping around; the first-ever assignment in a department starts at the
        first eligible agent."""

        stmt = (
            select(Ticket.assignee_id)
            .where(
                Ticket.branch_id == branch_id,
                Ticket.department_id == department_id,
                Ticket.assignee_id.in_(eligible),
            )
            .order_by(Ticket.updated_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        last_assignee_id = result.scalar_one_or_none()
        if last_assignee_id is None:
            return eligible[0]
        index = eligible.index(last_assignee_id)
        return eligible[(index + 1) % len(eligible)]

    async def auto_assign_ticket(self, ticket_id: UUID) -> Ticket | None:
        """Round-robins over active `ticket.own`-holding agents in the ticket's department who
        are not flagged unavailable (`data-model.md` has no separate "unavailable" column — an
        inactive user, `is_active=False`, is the only availability flag the schema models).
        Returns `None` (ticket stays unassigned) if none are eligible."""

        ticket = await self.session.get(Ticket, ticket_id)
        if ticket is None:
            return None

        eligible = await self._eligible_agents(ticket.branch_id, ticket.department_id)
        if not eligible:
            return None

        assignee_id = await self._next_in_rotation(ticket.branch_id, ticket.department_id, eligible)
        ticket.assignee_id = assignee_id
        self.session.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=None,
                event_type="assigned",
                new_value={"assignee_id": str(assignee_id)},
                visibility="internal",
                correlation_id=uuid4(),
                created_by=None,
            )
        )
        await self.session.flush()
        return ticket
