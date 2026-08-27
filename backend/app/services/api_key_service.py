from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audited
from app.core.errors import InvalidCredentialsError, NotFoundError
from app.core.permissions import CurrentActor, require_permission
from app.models.api_key import ApiKey as ApiKeyModel
from app.models.audit_log import AuditLog
from app.repositories.scoped_repository import TenantScope
from app.schemas.channel import ApiKeyCreate


def _hash_key(plaintext: str) -> str:
    """SHA-256, not Argon2 (`app/core/security.py`'s `hash_password`) — an issued API key is a
    high-entropy random secret (`secrets.token_urlsafe(32)` below), not a user-chosen low-entropy
    password, so it needs no slow/salted hash to resist guessing; a fast deterministic digest is
    what lets `authenticate()` look a key up by its hash directly (`WHERE key_hash = :hash`)
    instead of scanning every row and re-verifying against each one, which is what Argon2's
    per-call salt would otherwise force."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


class ApiKeyService:
    """plan.md §Service Classes — `ApiKeyService`. `issue`/`revoke` are admin-only
    (`x-permission: admin.config`, contracts/openapi.yaml); `authenticate` has no actor of its
    own — it is what `app/api/deps.py::get_current_actor` calls to build one from an `X-API-Key`
    header (T127)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _not_found(self, id: uuid.UUID) -> NotFoundError:
        return NotFoundError(f"مفتاح API غير موجود: {id}", f"API key not found: {id}")

    @require_permission("admin.config")
    async def list(self, actor: CurrentActor, limit: int = 50, offset: int = 0) -> list[ApiKeyModel]:
        result = await self.session.execute(select(ApiKeyModel).limit(limit).offset(offset))
        return list(result.scalars().all())

    @require_permission("admin.config")
    async def issue(self, actor: CurrentActor, data: ApiKeyCreate) -> tuple[ApiKeyModel, str]:
        """Not wrapped with `@audited` (unlike every other create in this codebase) — that
        decorator serializes a single `ModelT` as `after`, but this method's whole point is to
        return a `(row, plaintext)` pair, and the plaintext secret must never enter the audit
        row's `after` snapshot in the first place (it is returned to the caller "exactly once, in
        this response only", contracts/openapi.yaml). The `AuditLog` row is written manually
        instead, covering only the persisted columns — the same manual-`AuditLog` shape
        `UserService.grant_role` (app/services/user_service.py) already uses for a write whose
        return shape doesn't fit the decorator's single-entity assumption."""
        plaintext = secrets.token_urlsafe(32)
        row = ApiKeyModel(
            branch_id=data.branch_id,
            label=data.label,
            key_hash=_hash_key(plaintext),
            scopes=data.scopes,
            expires_at=data.expires_at,
            created_by=actor.user_id,
        )
        self.session.add(row)
        await self.session.flush()
        self.session.add(
            AuditLog(
                actor_id=actor.user_id,
                action="create",
                entity_type="api_key",
                entity_id=row.id,
                before=None,
                after={
                    "id": str(row.id),
                    "branch_id": str(row.branch_id) if row.branch_id else None,
                    "label": row.label,
                    "scopes": row.scopes,
                    "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                },
                correlation_id=actor.correlation_id,
            )
        )
        return row, plaintext

    @require_permission("admin.config")
    async def revoke(self, actor: CurrentActor, id: uuid.UUID) -> ApiKeyModel:
        return await self._revoke_audited(actor, id)

    @audited("api_key", "revoke")
    async def _revoke_audited(self, actor: CurrentActor, id: uuid.UUID) -> ApiKeyModel:
        row = await self.session.get(ApiKeyModel, id)
        if row is None:
            raise self._not_found(id)
        row.expires_at = datetime.now(UTC)
        row.updated_by = actor.user_id
        await self.session.flush()
        return row

    async def authenticate(self, plaintext_key: str) -> CurrentActor:
        result = await self.session.execute(
            select(ApiKeyModel).where(ApiKeyModel.key_hash == _hash_key(plaintext_key))
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise InvalidCredentialsError()
        if row.expires_at is not None and row.expires_at <= datetime.now(UTC):
            raise InvalidCredentialsError()

        row.last_used_at = datetime.now(UTC)
        await self.session.flush()

        return CurrentActor(
            user_id=row.id,
            scope=TenantScope(branch_id=row.branch_id, department_id=None),
            permissions=frozenset(row.scopes),
            correlation_id=uuid.uuid4(),
        )
