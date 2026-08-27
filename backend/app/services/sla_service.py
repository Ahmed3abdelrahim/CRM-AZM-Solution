from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time as dtime, timedelta
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audited
from app.core.errors import NotFoundError, ValidationError
from app.core.permissions import CurrentActor, require_permission
from app.models.branch import Branch
from app.models.priority import Priority
from app.models.role import Role
from app.models.sla_policy import SlaPolicy
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.ticket_status import TicketStatus
from app.models.user import User
from app.models.user_role import UserRole
from app.repositories.scoped_repository import TenantScope
from app.repositories.ticket_repository import TicketRepository

BreachState = Literal["on_track", "at_risk", "breached"]

_WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@dataclass(frozen=True)
class SlaDueDates:
    """`plan.md` §Service Classes — `SlaService.compute_due_dates`'s return shape. Never
    persisted (Principle XII) — `first_response_met`/`resolution_met` let
    `compute_breach_state` know a target no longer counts toward breach state without needing
    the `Ticket` row itself."""

    created_at: datetime
    first_response_due_at: datetime | None
    resolution_due_at: datetime | None
    first_response_met: bool
    resolution_met: bool


class SlaService:
    """plan.md §Service Classes — `SlaService`. `compute_due_dates`/`compute_breach_state` are
    pure functions over already-loaded rows (Principle XII — no SLA-state column exists
    anywhere; breach state is derived fresh on every call, including after a `docker compose
    restart` — nothing here is held only in memory)."""

    def __init__(self, session: AsyncSession, scope: TenantScope) -> None:
        self.session = session
        self.scope = scope
        self.repository = TicketRepository(session, scope)

    def _not_found(self, id: UUID) -> NotFoundError:
        return NotFoundError(f"التذكرة غير موجودة: {id}", f"Ticket not found: {id}")

    # ---------------------------------------------------------------- pure computation

    def compute_due_dates(self, ticket: Ticket, policy: SlaPolicy, branch: Branch) -> SlaDueDates:
        pause = timedelta(milliseconds=ticket.sla_paused_ms)

        if policy.business_hours_only:
            first_response_due_at = (
                self._add_business_minutes(
                    ticket.created_at, policy.first_response_minutes, branch.business_hours, branch.timezone
                )
                + pause
            )
            resolution_due_at = (
                self._add_business_minutes(
                    ticket.created_at, policy.resolution_minutes, branch.business_hours, branch.timezone
                )
                + pause
            )
        else:
            first_response_due_at = (
                ticket.created_at + timedelta(minutes=policy.first_response_minutes) + pause
            )
            resolution_due_at = ticket.created_at + timedelta(minutes=policy.resolution_minutes) + pause

        return SlaDueDates(
            created_at=ticket.created_at,
            first_response_due_at=first_response_due_at,
            resolution_due_at=resolution_due_at,
            first_response_met=ticket.first_response_at is not None,
            resolution_met=ticket.resolved_at is not None,
        )

    def compute_breach_state(self, due_dates: SlaDueDates, now: datetime) -> BreachState:
        states: list[BreachState] = []
        for due_at, met in (
            (due_dates.first_response_due_at, due_dates.first_response_met),
            (due_dates.resolution_due_at, due_dates.resolution_met),
        ):
            if met or due_at is None:
                continue
            total_seconds = (due_at - due_dates.created_at).total_seconds()
            remaining_seconds = (due_at - now).total_seconds()
            if remaining_seconds <= 0:
                states.append("breached")
            elif total_seconds > 0 and remaining_seconds <= total_seconds * 0.25:
                states.append("at_risk")
            else:
                states.append("on_track")

        if "breached" in states:
            return "breached"
        if "at_risk" in states:
            return "at_risk"
        return "on_track"

    def _add_business_minutes(
        self, start: datetime, minutes: int, business_hours: dict, tz_name: str
    ) -> datetime:
        """Walks forward `minutes` of business time only, per `branch.business_hours`/
        `branch.timezone` — outside those hours (incl. weekends absent from the map) never
        accrues (F05 acceptance #3)."""

        tz = ZoneInfo(tz_name)
        current = self._next_business_moment(start.astimezone(tz), business_hours)
        remaining = minutes

        while remaining > 0:
            day_key = _WEEKDAY_KEYS[current.weekday()]
            hours = business_hours.get(day_key)
            close_time = dtime.fromisoformat(hours["close"])
            close_dt = current.replace(
                hour=close_time.hour, minute=close_time.minute, second=0, microsecond=0
            )
            available_minutes = (close_dt - current).total_seconds() / 60
            if remaining <= available_minutes:
                current = current + timedelta(minutes=remaining)
                remaining = 0
            else:
                remaining -= available_minutes
                current = self._next_business_moment(self._start_of_next_day(close_dt), business_hours)

        return current.astimezone(UTC)

    def _start_of_next_day(self, dt: datetime) -> datetime:
        next_day = dt.date() + timedelta(days=1)
        return datetime.combine(next_day, dtime.min, tzinfo=dt.tzinfo)

    def _next_business_moment(self, dt: datetime, business_hours: dict) -> datetime:
        for _ in range(14):  # at most two weeks forward — always terminates for any real schedule
            day_key = _WEEKDAY_KEYS[dt.weekday()]
            hours = business_hours.get(day_key)
            if hours:
                open_time = dtime.fromisoformat(hours["open"])
                close_time = dtime.fromisoformat(hours["close"])
                open_dt = dt.replace(hour=open_time.hour, minute=open_time.minute, second=0, microsecond=0)
                close_dt = dt.replace(
                    hour=close_time.hour, minute=close_time.minute, second=0, microsecond=0
                )
                if dt < open_dt:
                    return open_dt
                if dt <= close_dt:
                    return dt
            dt = self._start_of_next_day(dt)
        raise ValidationError(
            "لا توجد ساعات عمل معرفة لهذا الفرع",
            "No business hours are configured for this branch",
        )

    # ---------------------------------------------------------------- policy resolution

    async def resolve_policy(
        self, branch_id: UUID, department_id: UUID, category_id: UUID, priority_id: UUID
    ) -> SlaPolicy | None:
        """Exact category+priority → priority-only → category-only → default (data-model.md
        §1.19 index) — a department-specific row always wins over the branch-wide (`NULL`
        department) default at the same tier."""

        department_pref = SlaPolicy.department_id.is_(None)
        for category_filter, priority_filter in (
            (SlaPolicy.category_id == category_id, SlaPolicy.priority_id == priority_id),
            (SlaPolicy.category_id.is_(None), SlaPolicy.priority_id == priority_id),
            (SlaPolicy.category_id == category_id, SlaPolicy.priority_id.is_(None)),
            (SlaPolicy.category_id.is_(None), SlaPolicy.priority_id.is_(None)),
        ):
            stmt = (
                select(SlaPolicy)
                .where(
                    SlaPolicy.branch_id == branch_id,
                    (SlaPolicy.department_id == department_id) | (SlaPolicy.department_id.is_(None)),
                    category_filter,
                    priority_filter,
                )
                .order_by(department_pref)
            )
            result = await self.session.execute(stmt)
            policy = result.scalars().first()
            if policy is not None:
                return policy
        return None

    @require_permission("ticket.sla_override")
    async def override_policy(
        self, actor: CurrentActor, ticket_id: UUID, sla_policy_id: UUID, reason: str
    ) -> Ticket:
        return await self._override_policy_audited(actor, ticket_id, sla_policy_id, reason)

    @audited("ticket", "sla_override")
    async def _override_policy_audited(
        self, actor: CurrentActor, id: UUID, sla_policy_id: UUID, reason: str
    ) -> Ticket:
        """FR-039 — existing policies only, reason required; recomputes both due dates from the
        ticket's original `created_at` under the new policy (deadlines are always derived at
        query time, never stored, so simply repointing `sla_policy_id` is the entire mechanism —
        an immediately-breaching result is permitted and picked up by the next
        `sweep_breaches()` run, per plan.md's "breach recording happens in exactly one place")."""

        ticket = await self.repository.get(id)
        if ticket is None:
            raise self._not_found(id)

        policy = await self.session.get(SlaPolicy, sla_policy_id)
        if policy is None or policy.branch_id != ticket.branch_id:
            raise ValidationError(
                "سياسة اتفاقية مستوى الخدمة المحددة غير موجودة لهذا الفرع",
                "The selected SLA policy does not exist for this branch",
            )

        old_policy_id = ticket.sla_policy_id
        updated = await self.repository.update(
            id, {"sla_policy_id": sla_policy_id, "updated_by": actor.user_id}
        )
        self.session.add(
            TicketEvent(
                ticket_id=id,
                actor_id=actor.user_id,
                event_type="field_changed",
                field_name="sla_policy_id",
                old_value={"value": str(old_policy_id) if old_policy_id else None},
                new_value={"value": str(sla_policy_id)},
                reason=reason,
                visibility="internal",
                correlation_id=actor.correlation_id,
                created_by=actor.user_id,
            )
        )
        await self.session.flush()

        from app.services.ticket_service import attach_computed_sla  # local: avoid import cycle

        return await attach_computed_sla(self.session, updated)

    # ---------------------------------------------------------------- breach sweep

    async def _raise_priority(self, ticket: Ticket) -> Priority | None:
        current = await self.session.get(Priority, ticket.priority_id)
        if current is None or current.severity <= 1:
            return None
        stmt = (
            select(Priority)
            .where(
                Priority.branch_id == ticket.branch_id,
                Priority.severity == current.severity - 1,
                (Priority.department_id == ticket.department_id) | (Priority.department_id.is_(None)),
            )
            .order_by(Priority.department_id.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def _department_lead_id(self, branch_id: UUID, department_id: UUID) -> UUID | None:
        stmt = (
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                Role.code == "lead",
                UserRole.branch_id == branch_id,
                UserRole.department_id == department_id,
                User.is_active.is_(True),
            )
            .order_by(User.id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def sweep_breaches(self) -> int:
        """`sla_sweep_job`'s body (every 5 minutes, F05). Idempotent by construction: an
        `sla_breached` event is written at most once per ticket per target
        (`field_name` = `'first_response'`/`'resolution'`) — a second run finds the existing
        event and writes nothing more (F05 acceptance #4)."""

        now = datetime.now(UTC)
        result = await self.session.execute(
            select(Ticket, SlaPolicy, Branch)
            .join(TicketStatus, TicketStatus.id == Ticket.status_id)
            .join(SlaPolicy, SlaPolicy.id == Ticket.sla_policy_id)
            .join(Branch, Branch.id == Ticket.branch_id)
            .where(TicketStatus.is_terminal.is_(False))
        )
        rows = result.all()

        written = 0
        for ticket, policy, branch in rows:
            due_dates = self.compute_due_dates(ticket, policy, branch)
            for target, due_at, met in (
                ("first_response", due_dates.first_response_due_at, due_dates.first_response_met),
                ("resolution", due_dates.resolution_due_at, due_dates.resolution_met),
            ):
                if met or due_at is None or now < due_at:
                    continue

                existing = await self.session.execute(
                    select(TicketEvent.id).where(
                        TicketEvent.ticket_id == ticket.id,
                        TicketEvent.event_type == "sla_breached",
                        TicketEvent.field_name == target,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                new_priority = await self._raise_priority(ticket)
                lead_id = await self._department_lead_id(ticket.branch_id, ticket.department_id)
                if new_priority is not None:
                    ticket.priority_id = new_priority.id
                if lead_id is not None:
                    ticket.assignee_id = lead_id

                self.session.add(
                    TicketEvent(
                        ticket_id=ticket.id,
                        actor_id=None,
                        event_type="sla_breached",
                        field_name=target,
                        new_value={
                            "priority_id": str(new_priority.id) if new_priority else None,
                            "assignee_id": str(lead_id) if lead_id else None,
                        },
                        visibility="internal",
                        # System-generated event — no CurrentActor to draw a correlation id from,
                        # and ticket_events.correlation_id is NOT NULL (data-model.md §1.17).
                        correlation_id=uuid4(),
                        created_by=None,
                    )
                )
                written += 1

        await self.session.flush()
        return written
