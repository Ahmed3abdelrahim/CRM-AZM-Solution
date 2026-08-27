from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.permissions import CurrentActor
from app.db import get_session
from app.schemas.kb_article import KbArticle, KbArticleCreate, KbArticleUpdate, KbSearchResult
from app.services.kb_service import KbService

router = APIRouter(tags=["kb"])


@router.get("/kb/articles", response_model=list[KbArticle], operation_id="listKbArticles")
async def list_kb_articles(
    limit: int = 50,
    offset: int = 0,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = KbService(session, actor.scope)
    return await service.list(actor, limit=limit, offset=offset)


@router.post(
    "/kb/articles", response_model=KbArticle, status_code=status.HTTP_201_CREATED, operation_id="createKbArticle"
)
async def create_kb_article(
    data: KbArticleCreate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = KbService(session, actor.scope)
    return await service.create_article(actor, data)


@router.get("/kb/articles/{id}", response_model=KbArticle, operation_id="getKbArticle")
async def get_kb_article(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = KbService(session, actor.scope)
    return await service.get(actor, id)


@router.patch("/kb/articles/{id}", response_model=KbArticle, operation_id="updateKbArticle")
async def update_kb_article(
    id: UUID,
    data: KbArticleUpdate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = KbService(session, actor.scope)
    return await service.update_article(actor, id, data)


@router.post("/kb/articles/{id}/publish", response_model=KbArticle, operation_id="publishKbArticle")
async def publish_kb_article(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = KbService(session, actor.scope)
    return await service.publish_article(actor, id)


@router.get("/kb/search", response_model=list[KbSearchResult], operation_id="searchKb")
async def search_kb(
    q: str = Query(...),
    limit: int = 10,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = KbService(session, actor.scope)
    return await service.search(actor, q, limit=limit)
