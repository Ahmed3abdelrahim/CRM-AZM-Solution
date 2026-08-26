from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.permissions import CurrentActor
from app.db import get_session
from app.schemas.role import (
    Branch,
    BranchCreate,
    BranchUpdate,
    Department,
    DepartmentCreate,
    DepartmentUpdate,
    Permission as PermissionSchema,
    Role,
    RoleCreate,
    RoleUpdate,
)
from app.schemas.user import User, UserCreate, UserRole, UserRoleCreate, UserUpdate
from app.services.admin_crud_service import AdminCrudService, BranchCrudService, DepartmentCrudService, RoleCrudService
from app.services.user_service import UserService

router = APIRouter(tags=["admin"])


def register_admin_crud_routes(
    router: APIRouter,
    *,
    path: str,
    service_cls: type[AdminCrudService],
    response_schema: type,
    create_schema: type,
    update_schema: type,
    remove_style: Literal["deactivate_post", "delete"],
    operation_ids: dict[str, str],
) -> None:
    """Registers the five Generic CRUD Pattern routes (list/create/get/update/remove) for one
    admin entity — every handler here does exactly what plan.md requires of a router: validate
    the request (via FastAPI's own schema parsing), delegate to one `AdminCrudService` method,
    serialize the result. No permission check or audit write happens in this file (§Shared
    Abstractions #2/#3) — both live inside the service methods being called."""

    @router.get(path, response_model=list[response_schema], operation_id=operation_ids["list"])
    async def _list(
        limit: int = 50,
        offset: int = 0,
        actor: CurrentActor = Depends(get_current_actor),
        session: AsyncSession = Depends(get_session),
    ):
        service = service_cls(session, actor.scope)
        return await service.list(actor, limit=limit, offset=offset)

    @router.post(
        path,
        response_model=response_schema,
        status_code=status.HTTP_201_CREATED,
        operation_id=operation_ids["create"],
    )
    async def _create(
        data: create_schema,
        actor: CurrentActor = Depends(get_current_actor),
        session: AsyncSession = Depends(get_session),
    ):
        service = service_cls(session, actor.scope)
        return await service.create(actor, data)

    @router.get(f"{path}/{{id}}", response_model=response_schema, operation_id=operation_ids["get"])
    async def _get(
        id: UUID,
        actor: CurrentActor = Depends(get_current_actor),
        session: AsyncSession = Depends(get_session),
    ):
        service = service_cls(session, actor.scope)
        return await service.get(actor, id)

    @router.patch(f"{path}/{{id}}", response_model=response_schema, operation_id=operation_ids["update"])
    async def _update(
        id: UUID,
        data: update_schema,
        actor: CurrentActor = Depends(get_current_actor),
        session: AsyncSession = Depends(get_session),
    ):
        service = service_cls(session, actor.scope)
        return await service.update(actor, id, data)

    if remove_style == "deactivate_post":

        @router.post(
            f"{path}/{{id}}/deactivate",
            response_model=response_schema,
            operation_id=operation_ids["remove"],
        )
        async def _deactivate(
            id: UUID,
            actor: CurrentActor = Depends(get_current_actor),
            session: AsyncSession = Depends(get_session),
        ):
            service = service_cls(session, actor.scope)
            return await service.remove(actor, id)
    else:

        @router.delete(
            f"{path}/{{id}}",
            status_code=status.HTTP_204_NO_CONTENT,
            operation_id=operation_ids["remove"],
            response_model=None,
        )
        async def _delete(
            id: UUID,
            actor: CurrentActor = Depends(get_current_actor),
            session: AsyncSession = Depends(get_session),
        ):
            service = service_cls(session, actor.scope)
            await service.remove(actor, id)


register_admin_crud_routes(
    router,
    path="/branches",
    service_cls=BranchCrudService,
    response_schema=Branch,
    create_schema=BranchCreate,
    update_schema=BranchUpdate,
    remove_style="deactivate_post",
    operation_ids={
        "list": "listBranches",
        "create": "createBranch",
        "get": "getBranch",
        "update": "updateBranch",
        "remove": "deactivateBranch",
    },
)

register_admin_crud_routes(
    router,
    path="/departments",
    service_cls=DepartmentCrudService,
    response_schema=Department,
    create_schema=DepartmentCreate,
    update_schema=DepartmentUpdate,
    remove_style="deactivate_post",
    operation_ids={
        "list": "listDepartments",
        "create": "createDepartment",
        "get": "getDepartment",
        "update": "updateDepartment",
        "remove": "deactivateDepartment",
    },
)

register_admin_crud_routes(
    router,
    path="/users",
    service_cls=UserService,
    response_schema=User,
    create_schema=UserCreate,
    update_schema=UserUpdate,
    remove_style="deactivate_post",
    operation_ids={
        "list": "listUsers",
        "create": "createUser",
        "get": "getUser",
        "update": "updateUser",
        "remove": "deactivateUser",
    },
)

register_admin_crud_routes(
    router,
    path="/roles",
    service_cls=RoleCrudService,
    response_schema=Role,
    create_schema=RoleCreate,
    update_schema=RoleUpdate,
    remove_style="delete",
    operation_ids={
        "list": "listRoles",
        "create": "createRole",
        "get": "getRole",
        "update": "updateRole",
        "remove": "deleteRole",
    },
)


# ---------------------------------------------------------------- users: role grants
@router.get("/users/{id}/roles", response_model=list[UserRole], operation_id="listUserRoles")
async def list_user_roles(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = UserService(session, actor.scope)
    return await service.list_roles(actor, id)


@router.post(
    "/users/{id}/roles",
    response_model=UserRole,
    status_code=status.HTTP_201_CREATED,
    operation_id="grantUserRole",
)
async def grant_user_role(
    id: UUID,
    data: UserRoleCreate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = UserService(session, actor.scope)
    return await service.grant_role(actor, id, data.role_id, data.branch_id, data.department_id)


# ---------------------------------------------------------------- roles: permission grants
@router.get(
    "/roles/{id}/permissions",
    response_model=list[PermissionSchema],
    operation_id="listRolePermissions",
)
async def list_role_permissions(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = RoleCrudService(session, actor.scope)
    return await service.list_permissions(actor, id)


@router.post(
    "/roles/{id}/permissions",
    status_code=status.HTTP_201_CREATED,
    operation_id="grantRolePermission",
)
async def grant_role_permission(
    id: UUID,
    permission_id: UUID = Body(..., embed=True),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = RoleCrudService(session, actor.scope)
    await service.grant_permission(actor, id, permission_id)
    return None


@router.get("/permissions", response_model=list[PermissionSchema], operation_id="listPermissions")
async def list_permissions(
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = RoleCrudService(session, actor.scope)
    return await service.list_all_permissions(actor)
