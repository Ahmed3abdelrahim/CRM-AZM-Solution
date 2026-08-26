import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.repositories.scoped_repository import TenantScope


@dataclass(frozen=True)
class CurrentActor:
    user_id: UUID
    scope: TenantScope
    permissions: frozenset[str]
    correlation_id: UUID


class PermissionDeniedError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def require_permission(code: str):
    """Wraps an async SERVICE method (never a route handler). The wrapped method's signature
    MUST be `(self, actor: CurrentActor, *args, **kwargs)`. Raises PermissionDeniedError(code)
    if `code` is not in `actor.permissions` — app/core/errors.py maps this to HTTP 403 with a
    localized ErrorResponse. On success, calls straight through with no other side effect."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(self, actor: CurrentActor, *args: Any, **kwargs: Any):
            if code not in actor.permissions:
                raise PermissionDeniedError(code)
            return await fn(self, actor, *args, **kwargs)

        return wrapper

    return decorator


def require_permission_via(code_selector: Callable[[Any], str]):
    """Identical to require_permission, except the permission code is read off the bound
    instance at call time via `code_selector(self)` instead of being a fixed literal — exists
    because AdminCrudService's decorated methods are defined once on the generic base class, but
    each subclass sets a different read_permission/write_permission class attribute."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(self, actor: CurrentActor, *args: Any, **kwargs: Any):
            code = code_selector(self)
            if code not in actor.permissions:
                raise PermissionDeniedError(code)
            return await fn(self, actor, *args, **kwargs)

        return wrapper

    return decorator
