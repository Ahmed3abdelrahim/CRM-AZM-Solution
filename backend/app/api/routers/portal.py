from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db import get_session
from app.schemas.kb_article import KbArticle
from app.schemas.portal import PortalTicketReceipt, PortalTicketSubmit, PortalTicketView
from app.services.portal_service import PortalService

router = APIRouter(tags=["portal"])


def _not_found() -> NotFoundError:
    # FR-053 — an unknown reference and a valid reference paired with the wrong contact method
    # produce an identical 404, never revealing which one occurred.
    return NotFoundError("لم يتم العثور على التذكرة", "Ticket not found")


@router.post(
    "/portal/tickets",
    response_model=PortalTicketReceipt,
    status_code=status.HTTP_201_CREATED,
    operation_id="submitPortalTicket",
)
async def submit_portal_ticket(data: PortalTicketSubmit, session: AsyncSession = Depends(get_session)):
    service = PortalService(session)
    reference_no = await service.submit_ticket(data)
    return PortalTicketReceipt(reference_no=reference_no)


@router.get(
    "/portal/tickets/{reference_no}", response_model=PortalTicketView, operation_id="trackPortalTicket"
)
async def track_portal_ticket(
    reference_no: str,
    contact_value: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    service = PortalService(session)
    result = await service.track_ticket(reference_no, contact_value)
    if result is None:
        raise _not_found()
    return result


@router.get(
    "/portal/customers/{reference_no}/history",
    response_model=list[PortalTicketView],
    operation_id="getPortalCustomerHistory",
)
async def get_portal_customer_history(
    reference_no: str,
    contact_value: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    service = PortalService(session)
    result = await service.get_history(reference_no, contact_value)
    if result is None:
        raise _not_found()
    return result


@router.get(
    "/portal/kb/articles", response_model=list[KbArticle], operation_id="listPortalKbArticles"
)
async def list_portal_kb_articles(session: AsyncSession = Depends(get_session)):
    service = PortalService(session)
    return await service.list_published_kb_articles()


@router.get(
    "/portal/kb/articles/{slug}", response_model=KbArticle, operation_id="getPortalKbArticle"
)
async def get_portal_kb_article(slug: str, session: AsyncSession = Depends(get_session)):
    service = PortalService(session)
    article = await service.get_published_kb_article_by_slug(slug)
    if article is None:
        raise NotFoundError("المقالة غير موجودة", "Article not found")
    return article
