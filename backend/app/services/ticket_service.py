from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from arq.connections import RedisSettings, create_pool
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.audit import audited
from app.core.errors import NotFoundError, ValidationError
from app.core.permissions import CurrentActor, require_permission
from app.core.storage import put_object
from app.models.attachment import Attachment
from app.models.category import Category
from app.models.customer import Customer
from app.models.priority import Priority
from app.models.sla_policy import SlaPolicy
from app.models.team import Team, TeamMember
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.ticket_status import TicketStatus
from app.repositories.scoped_repository import TenantScope
from app.repositories.ticket_repository import TicketFilters, TicketRepository
from app.schemas.ticket import TicketAssign, TicketCreate, TicketTriageCorrection, TicketUpdate


def attach_sla_placeholders(ticket: Ticket) -> Ticket:
    """Sets the three query-time-computed, never-stored SLA fields
    (`sla_first_response_due_at`/`sla_resolution_due_at`/`sla_breach_state`, contracts/
    openapi.yaml's `Ticket` schema) as plain instance attributes — not mapped columns, so this
    never touches a flush. Batch 4d has no `SlaService` yet (Batch 4f, T090), so every value is
    `None` here; `TicketTransitionService` (app/services/ticket_transition_service.py) calls this
    same helper so a status-changed response carries the identical (currently empty) shape."""

    ticket.sla_first_response_due_at = None
    ticket.sla_resolution_due_at = None
    ticket.sla_breach_state = None
    return ticket


def _enqueue_categorization_job(ticket_id: UUID) -> None:
    """Fire-and-forget (FR-049 — AI must never block ticket creation): schedules a background
    task that enqueues the ARQ job by name and returns immediately, without being awaited by the
    caller. Batch 4f (T096/T112) is what actually registers a `categorization_job` function on
    the worker (app/jobs/worker.py); enqueuing it by name here does not require it to exist yet —
    an unprocessed job simply waits in the queue. Any Redis failure is swallowed here rather than
    surfaced, for the same reason: AI/job-queue availability must never block ticket creation."""

    async def _enqueue() -> None:
        try:
            pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        except Exception:
            return
        try:
            await pool.enqueue_job("categorization_job", ticket_id)
        except Exception:
            pass
        finally:
            await pool.close()

    asyncio.create_task(_enqueue())


class TicketService:
    """plan.md §Service Classes — `TicketService`. Bespoke (not an `AdminCrudService` subclass):
    ticket creation carries FR-016's taxonomy validation, reference-number generation, SLA-policy
    resolution, and a fire-and-forget job enqueue that no generic CRUD flow models."""

    def __init__(self, session: AsyncSession, scope: TenantScope) -> None:
        self.session = session
        self.scope = scope
        self.repository = TicketRepository(session, scope)

    def _not_found(self, id: UUID) -> NotFoundError:
        return NotFoundError(f"التذكرة غير موجودة: {id}", f"Ticket not found: {id}")

    async def _validate_taxonomy(self, data: TicketCreate) -> None:
        """FR-016 — `category_id`/`priority_id` must each be currently active (a `Priority` row
        has no `is_active` column at all, data-model.md §1.13 — hard-delete means existence IS
        active) and, if department-scoped (its own `department_id` is not `NULL`), must match the
        ticket's `department_id`."""

        category = await self.session.get(Category, data.category_id)
        if category is None or category.branch_id != data.branch_id or not category.is_active:
            raise ValidationError(
                "التصنيف المحدد غير صالح أو غير نشط لهذا الفرع",
                "The selected category is invalid or inactive for this branch",
            )
        if category.department_id is not None and category.department_id != data.department_id:
            raise ValidationError(
                "التصنيف المحدد مخصص لقسم مختلف",
                "The selected category belongs to a different department",
            )

        priority = await self.session.get(Priority, data.priority_id)
        if priority is None or priority.branch_id != data.branch_id:
            raise ValidationError(
                "الأولوية المحددة غير صالحة لهذا الفرع",
                "The selected priority is invalid for this branch",
            )
        if priority.department_id is not None and priority.department_id != data.department_id:
            raise ValidationError(
                "الأولوية المحددة مخصصة لقسم مختلف",
                "The selected priority belongs to a different department",
            )

    async def _resolve_initial_status_id(self, branch_id: UUID, department_id: UUID) -> UUID:
        """The lowest-`sort_order` `ticket_statuses` row visible to this branch/department is
        treated as the workflow's starting state — data-driven via the column `data-model.md`
        §1.14 defines for exactly this kind of ordering, never a hardcoded status code
        (Principle XI)."""

        stmt = (
            select(TicketStatus.id)
            .where(
                TicketStatus.branch_id == branch_id,
                (TicketStatus.department_id == department_id) | (TicketStatus.department_id.is_(None)),
            )
            .order_by(TicketStatus.sort_order.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        status_id = result.scalar_one_or_none()
        if status_id is None:
            raise ValidationError(
                "لا توجد حالة تذاكر معرفة لهذا الفرع/القسم",
                "No ticket status is configured for this branch/department",
            )
        return status_id

    async def _resolve_sla_policy_stub(
        self, branch_id: UUID, department_id: UUID, category_id: UUID, priority_id: UUID
    ) -> UUID | None:
        """Batch 4d stub, completed for real in Batch 4f (T091): exact category+priority match
        only, department-specific row preferred over the `NULL`-department default. Batch 4f's
        `SlaService.resolve_policy` replaces this with the full exact → priority-only →
        category-only → default resolution order (data-model.md §1.19 index)."""

        stmt = (
            select(SlaPolicy.id)
            .where(
                SlaPolicy.branch_id == branch_id,
                SlaPolicy.category_id == category_id,
                SlaPolicy.priority_id == priority_id,
                (SlaPolicy.department_id == department_id) | (SlaPolicy.department_id.is_(None)),
            )
            .order_by(SlaPolicy.department_id.is_(None))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _generate_reference_no(self) -> str:
        """`TKT-{YYYY}-{6-digit sequence}` (data-model.md §1.16) — the numeric part comes from
        the DB sequence `ticket_reference_seq` (created in Batch 4a's migration); the year comes
        from the database's own clock in the same round trip, avoiding any app/DB clock skew."""

        result = await self.session.execute(
            select(func.nextval("ticket_reference_seq"), func.extract("year", func.now()))
        )
        seq, year = result.one()
        return f"TKT-{int(year)}-{int(seq):06d}"

    async def _resolve_actor_team_id(self, actor: CurrentActor) -> UUID | None:
        stmt = (
            select(TeamMember.team_id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(
                TeamMember.user_id == actor.user_id,
                Team.branch_id == actor.scope.branch_id,
                Team.department_id == actor.scope.department_id,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @require_permission("ticket.read")
    async def list(
        self,
        actor: CurrentActor,
        view: str | None,
        filters: TicketFilters | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Ticket]:
        if view == "my_open":
            return await self.repository.my_open(actor.user_id, filters, limit, offset)
        if view == "team_queue":
            team_id = await self._resolve_actor_team_id(actor)
            if team_id is None:
                return []
            return await self.repository.team_queue(team_id, filters, limit, offset)
        if view == "unassigned":
            return await self.repository.unassigned(filters, limit, offset)
        if view == "breaching_soon":
            return await self.repository.breaching_soon(filters, limit, offset)
        if view == "recently_closed":
            return await self.repository.recently_closed(filters, limit, offset)
        return await self.repository.list_filtered(filters, limit, offset)

    @require_permission("ticket.read")
    async def get(self, actor: CurrentActor, id: UUID) -> Ticket:
        ticket = await self.repository.get(id)
        if ticket is None:
            raise self._not_found(id)
        ticket.customer = await self.session.get(Customer, ticket.customer_id)  # FR-028
        return attach_sla_placeholders(ticket)

    @require_permission("ticket.create")
    async def create(self, actor: CurrentActor, data: TicketCreate) -> Ticket:
        await self._validate_taxonomy(data)
        return await self._create_audited(actor, None, data)

    @audited("ticket", "create")
    async def _create_audited(self, actor: CurrentActor, id: None, data: TicketCreate) -> Ticket:
        reference_no = await self._generate_reference_no()
        status_id = await self._resolve_initial_status_id(data.branch_id, data.department_id)
        sla_policy_id = await self._resolve_sla_policy_stub(
            data.branch_id, data.department_id, data.category_id, data.priority_id
        )

        values = data.model_dump()
        values.update(
            reference_no=reference_no,
            status_id=status_id,
            sla_policy_id=sla_policy_id,
            created_by=actor.user_id,
        )
        ticket = await self.repository.create(values)

        self.session.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=actor.user_id,
                event_type="created",
                visibility="customer",
                correlation_id=actor.correlation_id,
                created_by=actor.user_id,
            )
        )
        await self.session.flush()

        _enqueue_categorization_job(ticket.id)
        return attach_sla_placeholders(ticket)

    @require_permission("ticket.create")
    @audited("ticket", "update")
    async def update(self, actor: CurrentActor, id: UUID, data: TicketUpdate) -> Ticket:
        existing = await self.repository.get(id)
        if existing is None:
            raise self._not_found(id)
        values = data.model_dump(exclude_unset=True)
        values["updated_by"] = actor.user_id
        updated = await self.repository.update(id, values)
        return attach_sla_placeholders(updated)

    @require_permission("ticket.assign")
    async def assign(self, actor: CurrentActor, id: UUID, data: TicketAssign) -> Ticket:
        return await self._assign_audited(actor, id, data)

    @audited("ticket", "assign")
    async def _assign_audited(self, actor: CurrentActor, id: UUID, data: TicketAssign) -> Ticket:
        ticket = await self.repository.get(id)
        if ticket is None:
            raise self._not_found(id)
        values = data.model_dump(exclude_unset=True)
        if not values:
            return attach_sla_placeholders(ticket)

        was_assigned = ticket.assignee_id is not None
        values["updated_by"] = actor.user_id
        updated = await self.repository.update(id, values)

        new_value = {
            key: (str(value) if value is not None else None)
            for key, value in values.items()
            if key in ("assignee_id", "team_id")
        }
        self.session.add(
            TicketEvent(
                ticket_id=id,
                actor_id=actor.user_id,
                event_type="reassigned" if was_assigned else "assigned",
                new_value=new_value,
                visibility="internal",
                correlation_id=actor.correlation_id,
                created_by=actor.user_id,
            )
        )
        await self.session.flush()
        return attach_sla_placeholders(updated)

    @require_permission("ticket.read")
    async def add_note(self, actor: CurrentActor, id: UUID, body: str) -> TicketEvent:
        return await self._add_note_audited(actor, None, id, body)

    @audited("ticket_event", "create")
    async def _add_note_audited(self, actor: CurrentActor, id: None, ticket_id: UUID, body: str) -> TicketEvent:
        ticket = await self.repository.get(ticket_id)
        if ticket is None:
            raise self._not_found(ticket_id)
        event = TicketEvent(
            ticket_id=ticket_id,
            actor_id=actor.user_id,
            event_type="note_added",
            body=body,
            visibility="internal",
            correlation_id=actor.correlation_id,
            created_by=actor.user_id,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    @require_permission("ticket.read")
    async def add_reply(self, actor: CurrentActor, id: UUID, body: str) -> TicketEvent:
        return await self._add_reply_audited(actor, None, id, body)

    @audited("ticket_event", "create")
    async def _add_reply_audited(self, actor: CurrentActor, id: None, ticket_id: UUID, body: str) -> TicketEvent:
        ticket = await self.repository.get(ticket_id)
        if ticket is None:
            raise self._not_found(ticket_id)
        if ticket.first_response_at is None:  # FR-021 — set once, never overwritten
            ticket.first_response_at = datetime.now(UTC)
        event = TicketEvent(
            ticket_id=ticket_id,
            actor_id=actor.user_id,
            event_type="reply_sent",
            body=body,
            visibility="customer",
            correlation_id=actor.correlation_id,
            created_by=actor.user_id,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    @require_permission("ticket.read")
    async def add_attachment(self, actor: CurrentActor, id: UUID, file: UploadFile) -> Attachment:
        ticket = await self.repository.get(id)
        if ticket is None:
            raise self._not_found(id)
        return await self._add_attachment_audited(actor, None, ticket, file)

    @audited("attachment", "create")
    async def _add_attachment_audited(
        self, actor: CurrentActor, id: None, ticket: Ticket, file: UploadFile
    ) -> Attachment:
        data = await file.read()
        content_type = file.content_type or "application/octet-stream"
        storage_key = await asyncio.to_thread(put_object, data, content_type, prefix=f"tickets/{ticket.id}")

        attachment = Attachment(
            branch_id=ticket.branch_id,
            department_id=ticket.department_id,
            ticket_id=ticket.id,
            filename=file.filename or "attachment",
            content_type=content_type,
            size_bytes=len(data),
            storage_key=storage_key,
            uploaded_by=actor.user_id,
            created_by=actor.user_id,
        )
        self.session.add(attachment)
        self.session.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=actor.user_id,
                event_type="attachment_added",
                visibility="internal",
                correlation_id=actor.correlation_id,
                created_by=actor.user_id,
            )
        )
        await self.session.flush()
        return attachment

    @require_permission("ticket.assign")
    async def correct_triage(self, actor: CurrentActor, id: UUID, data: TicketTriageCorrection) -> Ticket:
        return await self._correct_triage_audited(actor, id, data)

    @audited("ticket", "correct_triage")
    async def _correct_triage_audited(
        self, actor: CurrentActor, id: UUID, data: TicketTriageCorrection
    ) -> Ticket:
        """FR-023c — clears `needs_triage` and records old/new values on the timeline, one
        `field_changed` event per field that actually changed."""

        ticket = await self.repository.get(id)
        if ticket is None:
            raise self._not_found(id)

        for field_name, new_value in (("branch_id", data.branch_id), ("department_id", data.department_id)):
            old_value = getattr(ticket, field_name)
            if old_value != new_value:
                self.session.add(
                    TicketEvent(
                        ticket_id=id,
                        actor_id=actor.user_id,
                        event_type="field_changed",
                        field_name=field_name,
                        old_value={"value": str(old_value)},
                        new_value={"value": str(new_value)},
                        visibility="internal",
                        correlation_id=actor.correlation_id,
                        created_by=actor.user_id,
                    )
                )

        updated = await self.repository.update(
            id,
            {
                "branch_id": data.branch_id,
                "department_id": data.department_id,
                "needs_triage": False,
                "updated_by": actor.user_id,
            },
        )
        await self.session.flush()
        return attach_sla_placeholders(updated)

    @require_permission("ticket.read")
    async def get_events(self, actor: CurrentActor, id: UUID) -> list[TicketEvent]:
        ticket = await self.repository.get(id)
        if ticket is None:
            raise self._not_found(id)
        result = await self.session.execute(
            select(TicketEvent).where(TicketEvent.ticket_id == id).order_by(TicketEvent.created_at)
        )
        return list(result.scalars().all())
