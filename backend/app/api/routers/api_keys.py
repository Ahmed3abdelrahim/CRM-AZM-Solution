from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.permissions import CurrentActor
from app.db import get_session
from app.schemas.channel import ApiKey, ApiKeyCreate, ApiKeyCreated
from app.services.api_key_service import ApiKeyService

router = APIRouter(tags=["api-keys"])


@router.get("/api-keys", response_model=list[ApiKey], operation_id="listApiKeys")
async def list_api_keys(
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = ApiKeyService(session)
    return await service.list(actor)


@router.post(
    "/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED, operation_id="createApiKey"
)
async def create_api_key(
    data: ApiKeyCreate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = ApiKeyService(session)
    row, plaintext_key = await service.issue(actor, data)
    return ApiKeyCreated(
        id=row.id,
        branch_id=row.branch_id,
        label=row.label,
        scopes=row.scopes,
        last_used_at=row.last_used_at,
        expires_at=row.expires_at,
        plaintext_key=plaintext_key,
    )


@router.post("/api-keys/{id}/revoke", response_model=ApiKey, operation_id="revokeApiKey")
async def revoke_api_key(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = ApiKeyService(session)
    return await service.revoke(actor, id)
