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
from app.schemas.quick_reply import QuickReply, QuickReplyCreate, QuickReplyUpdate
from app.schemas.team import Team, TeamCreate, TeamMemberCreate, TeamUpdate
from app.schemas.ticket_taxonomy import (
    Category,
    CategoryCreate,
    CategoryUpdate,
    Priority,
    PriorityCreate,
    PriorityUpdate,
    StatusTransition,
    StatusTransitionCreate,
    StatusTransitionUpdate,
    TicketStatus,
    TicketStatusCreate,
    TicketStatusUpdate,
)
from app.schemas.user import User, UserCreate, UserRole, UserRoleCreate, UserUpdate
from app.services.admin_crud_service import (
    AdminCrudService,
    BranchCrudService,
    CategoryCrudService,
    DepartmentCrudService,
    PriorityCrudService,
    QuickReplyCrudService,
    RoleCrudService,
    TeamCrudService,
    TicketStatusCrudService,
)
from app.services.status_transition_service import StatusTransitionService
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


# ---------------------------------------------------------------- Batch 4d: taxonomy + teams
register_admin_crud_routes(
    router,
    path="/categories",
    service_cls=CategoryCrudService,
    response_schema=Category,
    create_schema=CategoryCreate,
    update_schema=CategoryUpdate,
    remove_style="deactivate_post",
    operation_ids={
        "list": "listCategories",
        "create": "createCategory",
        "get": "getCategory",
        "update": "updateCategory",
        "remove": "deactivateCategory",
    },
)

register_admin_crud_routes(
    router,
    path="/priorities",
    service_cls=PriorityCrudService,
    response_schema=Priority,
    create_schema=PriorityCreate,
    update_schema=PriorityUpdate,
    remove_style="delete",
    operation_ids={
        "list": "listPriorities",
        "create": "createPriority",
        "get": "getPriority",
        "update": "updatePriority",
        "remove": "deletePriority",
    },
)

register_admin_crud_routes(
    router,
    path="/ticket-statuses",
    service_cls=TicketStatusCrudService,
    response_schema=TicketStatus,
    create_schema=TicketStatusCreate,
    update_schema=TicketStatusUpdate,
    remove_style="delete",
    operation_ids={
        "list": "listTicketStatuses",
        "create": "createTicketStatus",
        "get": "getTicketStatus",
        "update": "updateTicketStatus",
        "remove": "deleteTicketStatus",
    },
)

register_admin_crud_routes(
    router,
    path="/teams",
    service_cls=TeamCrudService,
    response_schema=Team,
    create_schema=TeamCreate,
    update_schema=TeamUpdate,
    remove_style="delete",
    operation_ids={
        "list": "listTeams",
        "create": "createTeam",
        "get": "getTeam",
        "update": "updateTeam",
        "remove": "deleteTeam",
    },
)


@router.post(
    "/teams/{id}/members",
    status_code=status.HTTP_201_CREATED,
    operation_id="addTeamMember",
)
async def add_team_member(
    id: UUID,
    data: TeamMemberCreate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = TeamCrudService(session, actor.scope)
    await service.add_member(actor, id, data.user_id)
    return None


# ---------------------------------------------------------------- Batch 4e: quick replies (F04)
register_admin_crud_routes(
    router,
    path="/quick-replies",
    service_cls=QuickReplyCrudService,
    response_schema=QuickReply,
    create_schema=QuickReplyCreate,
    update_schema=QuickReplyUpdate,
    remove_style="delete",
    operation_ids={
        "list": "listQuickReplies",
        "create": "createQuickReply",
        "get": "getQuickReply",
        "update": "updateQuickReply",
        "remove": "deleteQuickReply",
    },
)


# ---------------------------------------------------------------- status-transitions (no single-get)
@router.get(
    "/status-transitions", response_model=list[StatusTransition], operation_id="listStatusTransitions"
)
async def list_status_transitions(
    limit: int = 50,
    offset: int = 0,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = StatusTransitionService(session, actor.scope)
    return await service.list(actor, limit=limit, offset=offset)


@router.post(
    "/status-transitions",
    response_model=StatusTransition,
    status_code=status.HTTP_201_CREATED,
    operation_id="createStatusTransition",
)
async def create_status_transition(
    data: StatusTransitionCreate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = StatusTransitionService(session, actor.scope)
    return await service.create(actor, data)


@router.patch(
    "/status-transitions/{id}", response_model=StatusTransition, operation_id="updateStatusTransition"
)
async def update_status_transition(
    id: UUID,
    data: StatusTransitionUpdate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = StatusTransitionService(session, actor.scope)
    return await service.update(actor, id, data)


@router.delete(
    "/status-transitions/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteStatusTransition",
    response_model=None,
)
async def delete_status_transition(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = StatusTransitionService(session, actor.scope)
    await service.delete(actor, id)
