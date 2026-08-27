from __future__ import annotations

import dataclasses
import uuid

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import CurrentActor
from app.core.security import InvalidTokenError, decode_token
from app.db import get_session
from app.models.role import Permission, RolePermission
from app.models.user import User
from app.models.user_role import UserRole
from app.repositories.scoped_repository import TenantScope
from app.services.api_key_service import ApiKeyService


def _correlation_id(request: Request) -> uuid.UUID:
    raw = getattr(request.state, "correlation_id", None)
    try:
        return uuid.UUID(str(raw)) if raw else uuid.uuid4()
    except ValueError:
        # A client-supplied X-Correlation-Id that isn't a UUID — fall back rather than 500.
        return uuid.uuid4()


async def get_current_actor(
    request: Request,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> CurrentActor:
    """Decodes a bearer JWT into a CurrentActor. `permissions` is the union of
    `role_permissions` reachable via every `user_roles` row matching the user's own home
    branch/department (data-model.md §1.3/§1.7) — plan.md §Shared Abstractions #2.

    `X-API-Key` (T127, Batch 4i) is checked first: `contracts/openapi.yaml`'s `ApiKeyAuth`
    security scheme is only ever combined with a request that also carries no bearer token
    (`/channels/inbound`), so there is no real ambiguity between the two — but checking the
    header's mere presence up front means a request that sends both an (irrelevant) bearer token
    and a valid API key still authenticates via the key, matching what the caller explicitly
    asked for."""

    if x_api_key is not None:
        actor = await ApiKeyService(session).authenticate(x_api_key)
        return dataclasses.replace(actor, correlation_id=_correlation_id(request))

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()

    try:
        user_id = decode_token(token, expected_type="access")
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user.id, UserRole.branch_id == user.branch_id)
    )
    if user.department_id is not None:
        stmt = stmt.where(UserRole.department_id == user.department_id)
    result = await session.execute(stmt)
    permissions = frozenset(result.scalars().all())

    return CurrentActor(
        user_id=user.id,
        scope=TenantScope(branch_id=user.branch_id, department_id=user.department_id),
        permissions=permissions,
        correlation_id=_correlation_id(request),
    )
