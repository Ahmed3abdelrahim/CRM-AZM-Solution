from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audited
from app.core.errors import NotFoundError
from app.core.permissions import CurrentActor, require_permission
from app.models.status_transition import StatusTransition
from app.repositories.scoped_repository import ScopedRepository, ScopingMode, TenantScope
from app.schemas.ticket_taxonomy import StatusTransitionCreate, StatusTransitionUpdate


class StatusTransitionRepository(ScopedRepository[StatusTransition]):
    model = StatusTransition
    scoping_mode = ScopingMode.S2_BRANCH_DEPT_OPTIONAL
    has_soft_delete = False


class StatusTransitionService:
    """Admin-side CRUD over `status_transitions` — `list`/`create`/`update`/`delete` only, no
    single-`get` (matching contracts/openapi.yaml). Not an `AdminCrudService` subclass because
    the missing `get` breaks that base class's assumed five-method shape; `delete` is a hard
    `DELETE` (no `is_active` column, data-model.md §1.15).

    `TicketTransitionService` (app/services/ticket_transition_service.py) is the ONLY class that
    reads this table to decide legality (Principle XI) — this service exists purely for admins to
    configure the rows it reads.
    """

    entity_type = "status_transition"

    def __init__(self, session: AsyncSession, scope: TenantScope) -> None:
        self.session = session
        self.repository = StatusTransitionRepository(session, scope)

    def _not_found(self, id: UUID) -> NotFoundError:
        return NotFoundError(f"قاعدة الانتقال غير موجودة: {id}", f"Status transition not found: {id}")

    @require_permission("status_transition.read")
    async def list(self, actor: CurrentActor, limit: int = 50, offset: int = 0) -> list[StatusTransition]:
        return await self.repository.list(limit=limit, offset=offset)

    @require_permission("admin.config")
    async def create(self, actor: CurrentActor, data: StatusTransitionCreate) -> StatusTransition:
        return await self._create_audited(actor, None, data)

    @audited("status_transition", "create")
    async def _create_audited(
        self, actor: CurrentActor, id: None, data: StatusTransitionCreate
    ) -> StatusTransition:
        values = data.model_dump()
        values["created_by"] = actor.user_id
        return await self.repository.create(values)

    @require_permission("admin.config")
    @audited("status_transition", "update")
    async def update(self, actor: CurrentActor, id: UUID, data: StatusTransitionUpdate) -> StatusTransition:
        existing = await self.repository.get(id)
        if existing is None:
            raise self._not_found(id)
        values = data.model_dump(exclude_unset=True)
        values["updated_by"] = actor.user_id
        return await self.repository.update(id, values)

    @require_permission("admin.config")
    async def delete(self, actor: CurrentActor, id: UUID) -> None:
        return await self._delete_audited(actor, id)

    @audited("status_transition", "delete")
    async def _delete_audited(self, actor: CurrentActor, id: UUID) -> None:
        existing = await self.repository.get(id)
        if existing is None:
            raise self._not_found(id)
        await self.repository.delete(id)
        return None
