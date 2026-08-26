from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audited
from app.core.errors import IllegalTransitionError, NotFoundError, ValidationError
from app.core.permissions import CurrentActor, PermissionDeniedError, require_permission
from app.models.status_transition import StatusTransition
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.ticket_status import TicketStatus
from app.repositories.scoped_repository import TenantScope
from app.repositories.ticket_repository import TicketRepository
from app.services.ticket_service import attach_sla_placeholders


class TicketTransitionService:
    """plan.md §Service Classes — `TicketTransitionService`. `change_status` is the ONLY method
    in the entire codebase that queries `status_transitions` (Principle XI) — no status code or
    transition is ever hardcoded in application code."""

    def __init__(self, session: AsyncSession, scope: TenantScope) -> None:
        self.session = session
        self.scope = scope
        self.repository = TicketRepository(session, scope)

    def _not_found(self, id: UUID) -> NotFoundError:
        return NotFoundError(f"التذكرة غير موجودة: {id}", f"Ticket not found: {id}")

    @require_permission("ticket.read")
    async def change_status(
        self, actor: CurrentActor, id: UUID, to_status_id: UUID, reason: str | None
    ) -> Ticket:
        return await self._change_status_audited(actor, id, to_status_id, reason)

    @audited("ticket", "status_changed")
    async def _change_status_audited(
        self, actor: CurrentActor, id: UUID, to_status_id: UUID, reason: str | None
    ) -> Ticket:
        ticket = await self.repository.get(id)
        if ticket is None:
            raise self._not_found(id)

        from_status_id = ticket.status_id
        same_department_or_default = (StatusTransition.department_id == ticket.department_id) | (
            StatusTransition.department_id.is_(None)
        )

        matched_result = await self.session.execute(
            select(StatusTransition)
            .where(
                StatusTransition.branch_id == ticket.branch_id,
                StatusTransition.from_status_id == from_status_id,
                StatusTransition.to_status_id == to_status_id,
                same_department_or_default,
            )
            .order_by(StatusTransition.department_id.is_(None))  # department-specific row first
        )
        matched = matched_result.scalars().first()

        if matched is None:
            permitted_result = await self.session.execute(
                select(StatusTransition.to_status_id).where(
                    StatusTransition.branch_id == ticket.branch_id,
                    StatusTransition.from_status_id == from_status_id,
                    same_department_or_default,
                )
            )
            permitted_status_ids = list(dict.fromkeys(permitted_result.scalars().all()))
            raise IllegalTransitionError(
                "الانتقال إلى هذه الحالة غير مسموح به من الحالة الحالية للتذكرة",
                "This transition is not permitted from the ticket's current status",
                current_status_id=from_status_id,
                permitted_status_ids=permitted_status_ids,
            )

        if matched.required_permission is not None and matched.required_permission not in actor.permissions:
            raise PermissionDeniedError(matched.required_permission)

        if matched.requires_reason and not reason:
            raise ValidationError(
                "يجب إدخال سبب لهذا الانتقال",
                "A reason is required for this status transition",
            )

        to_status = await self.session.get(TicketStatus, to_status_id)

        values: dict = {"status_id": to_status_id, "updated_by": actor.user_id}
        if to_status is not None and to_status.is_terminal and ticket.closed_at is None:
            values["closed_at"] = datetime.now(UTC)
        if matched.required_permission == "ticket.reopen":
            # data-model.md §5.1 — the only pair of transitions gated by ticket.reopen ARE the
            # reopen transitions (resolved/closed -> reopened); reusing this data-driven field
            # avoids special-casing the "reopened" status code (Principle XI).
            values["reopened_count"] = ticket.reopened_count + 1

        updated = await self.repository.update(id, values)

        self.session.add(
            TicketEvent(
                ticket_id=id,
                actor_id=actor.user_id,
                event_type="status_changed",
                old_value={"status_id": str(from_status_id)},
                new_value={"status_id": str(to_status_id)},
                reason=reason,
                visibility="customer",
                correlation_id=actor.correlation_id,
                created_by=actor.user_id,
            )
        )
        await self.session.flush()
        return attach_sla_placeholders(updated)
