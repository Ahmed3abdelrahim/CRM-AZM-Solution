from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audited_via
from app.core.errors import NotFoundError
from app.core.permissions import CurrentActor, require_permission, require_permission_via
from app.models.branch import Branch
from app.models.department import Department
from app.models.role import Permission, Role, RolePermission
from app.repositories.scoped_repository import ScopedRepository, ScopingMode, TenantScope

ModelT = TypeVar("ModelT")
CreateSchemaT = TypeVar("CreateSchemaT")
UpdateSchemaT = TypeVar("UpdateSchemaT")


class AdminCrudService(Generic[ModelT, CreateSchemaT, UpdateSchemaT]):
    """plan.md §Generic CRUD Pattern. Every subclass is *thin*: it sets `repository_cls`,
    `entity_type`, `read_permission` as class attributes only (`write_permission` inherits
    "admin.config" unchanged) — `list`/`get`/`update`/`remove` below are never overridden;
    `UserService` (app/services/user_service.py) is the one subclass that customizes `create`,
    and it does so via the `_to_create_values` hook rather than overriding `create` itself, so
    the permission/audit wiring stays identical for every subclass.

    `__init__` takes `scope`, not just `session` — every S1/S2/S3-scoped admin entity (e.g.
    `departments`) still goes through `ScopedRepository`'s normal branch/department filtering
    (Principle V — no admin exception; PLAN.md's `cross_branch` escape hatch is reserved for
    `ReportService` only, per plan.md §Post-Design Constitution Check). Building `self.repository`
    here — rather than per-call — is also what lets `audited_via`'s "before" snapshot fetch find
    `self.repository` already in place before the wrapped method body runs.
    """

    repository_cls: ClassVar[type[ScopedRepository]]
    read_permission: ClassVar[str]
    write_permission: ClassVar[str] = "admin.config"
    entity_type: ClassVar[str]

    def __init__(self, session: AsyncSession, scope: TenantScope) -> None:
        self.session = session
        self.repository = self.repository_cls(session, scope)

    def _to_create_values(self, actor: CurrentActor, data: CreateSchemaT) -> dict[str, Any]:
        values = dict(data.model_dump())
        values["created_by"] = actor.user_id
        return values

    def _to_update_values(self, actor: CurrentActor, data: UpdateSchemaT) -> dict[str, Any]:
        values = dict(data.model_dump(exclude_unset=True))
        values["updated_by"] = actor.user_id
        return values

    def _not_found(self, id: UUID) -> NotFoundError:
        return NotFoundError(
            f"{self.entity_type} غير موجود: {id}",
            f"{self.entity_type} not found: {id}",
        )

    @require_permission_via(lambda self: self.read_permission)
    async def list(
        self,
        actor: CurrentActor,
        filters: Mapping[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ModelT]:
        return await self.repository.list(filters=filters, limit=limit, offset=offset)

    @require_permission_via(lambda self: self.read_permission)
    async def get(self, actor: CurrentActor, id: UUID) -> ModelT:
        instance = await self.repository.get(id)
        if instance is None:
            raise self._not_found(id)
        return instance

    @require_permission_via(lambda self: self.write_permission)
    async def create(self, actor: CurrentActor, data: CreateSchemaT) -> ModelT:
        return await self._create_audited(actor, None, data)

    @audited_via(lambda self: self.entity_type, "create")
    async def _create_audited(self, actor: CurrentActor, id: None, data: CreateSchemaT) -> ModelT:
        values = self._to_create_values(actor, data)
        return await self.repository.create(values)

    @require_permission_via(lambda self: self.write_permission)
    @audited_via(lambda self: self.entity_type, "update")
    async def update(self, actor: CurrentActor, id: UUID, data: UpdateSchemaT) -> ModelT:
        existing = await self.repository.get(id)
        if existing is None:
            raise self._not_found(id)
        values = self._to_update_values(actor, data)
        return await self.repository.update(id, values)

    @require_permission_via(lambda self: self.write_permission)
    @audited_via(lambda self: self.entity_type, "remove")
    async def remove(self, actor: CurrentActor, id: UUID) -> ModelT | None:
        existing = await self.repository.get(id)
        if existing is None:
            raise self._not_found(id)
        if self.repository_cls.has_soft_delete:
            return await self.repository.deactivate(id)
        await self.repository.delete(id)
        return None


class _BranchRepository(ScopedRepository[Branch]):
    model = Branch
    scoping_mode = ScopingMode.S6_GLOBAL
    has_soft_delete = True


class BranchCrudService(AdminCrudService[Branch, Any, Any]):
    repository_cls = _BranchRepository
    entity_type = "branch"
    read_permission = "branch.read"


class _DepartmentRepository(ScopedRepository[Department]):
    model = Department
    scoping_mode = ScopingMode.S3_BRANCH_ONLY
    has_soft_delete = True


class DepartmentCrudService(AdminCrudService[Department, Any, Any]):
    repository_cls = _DepartmentRepository
    entity_type = "department"
    read_permission = "department.read"


class _RoleRepository(ScopedRepository[Role]):
    model = Role
    scoping_mode = ScopingMode.S6_GLOBAL
    has_soft_delete = False


class RoleCrudService(AdminCrudService[Role, Any, Any]):
    """Thin CRUD subclass plus the role↔permission management surface (`/roles/{id}/permissions`,
    `/permissions`) — bespoke because `role_permissions`/`permissions` have no CRUD schema of
    their own in contracts/openapi.yaml, only these two read/grant operations."""

    repository_cls = _RoleRepository
    entity_type = "role"
    read_permission = "role.read"

    @require_permission("admin.config")
    async def list_permissions(self, actor: CurrentActor, role_id: UUID) -> list[Permission]:
        stmt = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    @require_permission("admin.config")
    async def grant_permission(self, actor: CurrentActor, role_id: UUID, permission_id: UUID) -> RolePermission:
        row = RolePermission(role_id=role_id, permission_id=permission_id, created_by=actor.user_id)
        self.session.add(row)
        await self.session.flush()
        return row

    @require_permission("admin.config")
    async def list_all_permissions(self, actor: CurrentActor) -> list[Permission]:
        result = await self.session.execute(select(Permission))
        return list(result.scalars().all())
