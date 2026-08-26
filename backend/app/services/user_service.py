from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.permissions import CurrentActor, require_permission
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.user_role import UserRole
from app.repositories.scoped_repository import ScopedRepository, ScopingMode
from app.schemas.user import UserCreate, UserUpdate
from app.services.admin_crud_service import AdminCrudService


class UserRepository(ScopedRepository[User]):
    model = User
    scoping_mode = ScopingMode.S2_BRANCH_DEPT_OPTIONAL
    has_soft_delete = True


class UserService(AdminCrudService[User, UserCreate, UserUpdate]):
    """plan.md §Generic CRUD Pattern — overrides only the create-value mapping, to Argon2-hash
    `password`→`password_hash` before the inherited, unchanged permission/audit-wrapped
    `create()` delegates to `repository.create()`."""

    repository_cls = UserRepository
    entity_type = "user"
    read_permission = "user.read"

    def _to_create_values(self, actor: CurrentActor, data: UserCreate) -> dict[str, Any]:
        values = dict(data.model_dump(exclude={"password"}))
        values["password_hash"] = hash_password(data.password)
        values["created_by"] = actor.user_id
        return values

    @require_permission("admin.config")
    async def list_roles(self, actor: CurrentActor, user_id: UUID) -> list[UserRole]:
        result = await self.session.execute(select(UserRole).where(UserRole.user_id == user_id))
        return list(result.scalars().all())

    @require_permission("admin.config")
    async def grant_role(
        self,
        actor: CurrentActor,
        user_id: UUID,
        role_id: UUID,
        branch_id: UUID,
        department_id: UUID,
    ) -> UserRole:
        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            branch_id=branch_id,
            department_id=department_id,
            created_by=actor.user_id,
        )
        self.session.add(user_role)
        await self.session.flush()
        self.session.add(
            AuditLog(
                actor_id=actor.user_id,
                action="create",
                entity_type="user_role",
                entity_id=user_role.id,
                before=None,
                after={
                    "id": str(user_role.id),
                    "user_id": str(user_role.user_id),
                    "role_id": str(user_role.role_id),
                    "branch_id": str(user_role.branch_id),
                    "department_id": str(user_role.department_id),
                },
                correlation_id=actor.correlation_id,
            )
        )
        return user_role
