from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.permissions import CurrentActor
from app.db import get_session
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenPair:
    return await AuthService(session).login(data.email, data.password)


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(data: RefreshRequest, session: AsyncSession = Depends(get_session)) -> TokenPair:
    return await AuthService(session).refresh(data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def logout(
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
) -> None:
    await AuthService(session).logout(actor)
