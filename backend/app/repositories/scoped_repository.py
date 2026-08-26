from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Generic, TypeVar
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class ScopingMode(str, Enum):
    """PLAN.md §4.1 / data-model.md §0.7 — the six tenant-scoping patterns."""

    S1_FULL = "s1_full"
    S2_BRANCH_DEPT_OPTIONAL = "s2_branch_dept_optional"
    S3_BRANCH_ONLY = "s3_branch_only"
    S4_TRANSITIVE = "s4_transitive"
    S5_SYSTEM_NULLABLE = "s5_system_nullable"
    S6_GLOBAL = "s6_global"


@dataclass(frozen=True)
class TenantScope:
    branch_id: UUID | None
    department_id: UUID | None
    cross_branch: bool = False


class ScopedRepository(Generic[ModelT]):
    """Plan.md §Shared Abstractions #1 — the only place any branch/department/parent-join
    predicate is added to a query anywhere in the codebase.

    Every entity repository is `ScopedRepository[Model]` instantiated with `model`/
    `scoping_mode`/`parent_model`/`parent_fk_column`/`has_soft_delete` set as class attributes —
    no subclass writes its own WHERE. Every such subclass is auto-registered by `model` so an
    S4 repository can recursively resolve its parent's own scoping predicate (S4-of-S4 resolves
    correctly, even though none currently exist in this schema).
    """

    model: ClassVar[type[Any]]
    scoping_mode: ClassVar[ScopingMode]
    parent_model: ClassVar[type[Any] | None] = None
    parent_fk_column: ClassVar[str | None] = None
    has_soft_delete: ClassVar[bool] = False

    _registry: ClassVar[dict[type[Any], type["ScopedRepository"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        model = cls.__dict__.get("model")
        if model is not None:
            ScopedRepository._registry[model] = cls

    def __init__(self, session: AsyncSession, scope: TenantScope) -> None:
        self.session = session
        self.scope = scope

    def _scoped_select(self) -> Select[tuple[ModelT]]:
        stmt: Select[tuple[ModelT]] = select(self.model)
        mode = self.scoping_mode

        if mode is ScopingMode.S6_GLOBAL:
            return stmt

        if mode is ScopingMode.S4_TRANSITIVE:
            if self.parent_model is None or self.parent_fk_column is None:
                raise ValueError(f"{self.model.__name__}: S4 requires parent_model and parent_fk_column")
            parent_repo_cls = ScopedRepository._registry.get(self.parent_model)
            if parent_repo_cls is None:
                raise ValueError(f"No ScopedRepository registered for parent {self.parent_model.__name__}")
            parent_repo = parent_repo_cls(self.session, self.scope)
            parent_stmt = parent_repo._scoped_select()

            child_fk = getattr(self.model, self.parent_fk_column)
            stmt = stmt.join(self.parent_model, child_fk == self.parent_model.id)
            if parent_stmt.whereclause is not None:
                stmt = stmt.where(parent_stmt.whereclause)
            return stmt

        if not self.scope.cross_branch:
            if mode is ScopingMode.S1_FULL:
                stmt = stmt.where(
                    self.model.branch_id == self.scope.branch_id,
                    self.model.department_id == self.scope.department_id,
                )
            elif mode is ScopingMode.S2_BRANCH_DEPT_OPTIONAL:
                stmt = stmt.where(self.model.branch_id == self.scope.branch_id).where(
                    (self.model.department_id == self.scope.department_id)
                    | (self.model.department_id.is_(None))
                )
            elif mode is ScopingMode.S3_BRANCH_ONLY:
                stmt = stmt.where(self.model.branch_id == self.scope.branch_id)
            elif mode is ScopingMode.S5_SYSTEM_NULLABLE:
                stmt = stmt.where(
                    (self.model.branch_id == self.scope.branch_id) | (self.model.branch_id.is_(None))
                )
        return stmt

    async def get(self, id: UUID) -> ModelT | None:
        stmt = self._scoped_select().where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        filters: Mapping[str, Any] | None = None,
        order_by: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ModelT]:
        stmt = self._scoped_select()
        if filters:
            for key, value in filters.items():
                stmt = stmt.where(getattr(self.model, key) == value)
        if order_by:
            stmt = stmt.order_by(getattr(self.model, order_by))
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, values: Mapping[str, Any]) -> ModelT:
        instance = self.model(**values)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, id: UUID, values: Mapping[str, Any]) -> ModelT:
        instance = await self.get(id)
        if instance is None:
            raise ValueError(f"{self.model.__name__} {id} not found")
        for key, value in values.items():
            setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def deactivate(self, id: UUID) -> ModelT:
        """Sets is_active=False. Raises NotImplementedError if has_soft_delete is False —
        use delete() instead (data-model.md §0.4's hard-delete tables)."""
        if not self.has_soft_delete:
            raise NotImplementedError(f"{self.model.__name__} has no is_active column — use delete()")
        return await self.update(id, {"is_active": False})

    async def delete(self, id: UUID) -> None:
        """Hard DELETE. Raises NotImplementedError if has_soft_delete is True — use
        deactivate() instead. Lets the DB's ON DELETE RESTRICT surface as an IntegrityError,
        mapped by app/core/errors.py to a 409 with a localized message."""
        if self.has_soft_delete:
            raise NotImplementedError(f"{self.model.__name__} has is_active — use deactivate()")
        instance = await self.get(id)
        if instance is None:
            raise ValueError(f"{self.model.__name__} {id} not found")
        await self.session.delete(instance)
        await self.session.flush()
