import datetime
import functools
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import inspect

from app.models.audit_log import AuditLog
from app.repositories.scoped_repository import ScopedRepository


def _serialize(instance: Any) -> dict[str, Any] | None:
    if instance is None:
        return None
    mapper = inspect(instance).mapper
    result: dict[str, Any] = {}
    for column in mapper.columns:
        value = getattr(instance, column.key)
        if isinstance(value, (uuid.UUID, datetime.date, datetime.time)):
            value = str(value)
        result[column.key] = value
    return result


def audited(entity_type: str, action: str):
    """Plan.md §Shared Abstractions #3. Wraps an async SERVICE method already wrapped by (or
    itself calling) require_permission, whose signature is
    `(self, actor: CurrentActor, id: UUID | None, *args, **kwargs) -> ModelT | None`.

    All inside the SAME AsyncSession/transaction as the wrapped call (never a separate commit):
      1. If id is not None, load the entity's current row as `before` (None if it doesn't exist
         yet — the create case).
      2. Call the wrapped method; let any exception propagate uncaught — the transaction rolls
         back, so no audit row is written.
      3. Serialize the result as `after`.
      4. session.add(AuditLog(...)) — added to the session, not committed independently; the
         request-scoped get_session() dependency commits once, at the end of the request.
      5. Return the wrapped method's result unchanged.
    """
    return audited_via(lambda self: entity_type, action)


def audited_via(entity_type_selector: Callable[[Any], str], action: str):
    """Identical to `audited`, except entity_type is read off the bound instance at call time
    via `entity_type_selector(self)` instead of being a fixed literal — the audit-write analogue
    of `require_permission_via` (app/core/permissions.py). Needed because
    `AdminCrudService.update`/`.remove` (app/services/admin_crud_service.py) are defined once on
    the generic base class, but each subclass (BranchCrudService, DepartmentCrudService, ...)
    sets a different `entity_type` class attribute — a literal `entity_type` captured at
    decoration time on the base class could never see a subclass's value."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(self, actor, id: uuid.UUID | None, *args: Any, **kwargs: Any):
            entity_type = entity_type_selector(self)
            repository: ScopedRepository | None = getattr(self, "repository", None)
            before = None
            if id is not None and repository is not None:
                existing = await repository.get(id)
                before = _serialize(existing)

            result = await fn(self, actor, id, *args, **kwargs)

            if result is not None:
                # A column with onupdate=func.now() (UpdatedMixin.updated_at) is left expired
                # after an UPDATE flush — SQLAlchemy 2.0's eager_defaults="auto" only fetches
                # server-generated values back via RETURNING on INSERT, not UPDATE. Reading an
                # expired attribute from here (plain sync code, not inside session.flush()'s own
                # await chain) raises MissingGreenlet under the async driver. refresh() re-fetches
                # every column in one more SELECT, sidestepping the lazy-load entirely.
                await self.session.refresh(result)

            after = _serialize(result)
            entity_id = result.id if result is not None else id

            self.session.add(
                AuditLog(
                    actor_id=actor.user_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    before=before,
                    after=after,
                    correlation_id=actor.correlation_id,
                )
            )
            return result

        return wrapper

    return decorator
