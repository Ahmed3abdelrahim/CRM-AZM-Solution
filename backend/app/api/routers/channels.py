from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.channels.base import ChannelEnum
from app.core.permissions import CurrentActor, PermissionDeniedError
from app.db import get_session
from app.schemas.channel import InboundMessageAccepted, NormalizedMessagePayload
from app.services.channel_service import ChannelService

router = APIRouter(tags=["channels"])


@router.post(
    "/channels/inbound",
    response_model=InboundMessageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="postInboundMessage",
)
async def post_inbound_message(
    data: NormalizedMessagePayload,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    """`security: [ApiKeyAuth]`, `x-permission: ticket.create` (contracts/openapi.yaml) — enforced
    here rather than via a `@require_permission` on `ChannelService.ingest()` itself, since that
    method's other caller (`poll_email()`, a background job) has no `CurrentActor` at all."""
    if "ticket.create" not in actor.permissions:
        raise PermissionDeniedError("ticket.create")

    service = ChannelService(session)
    return await service.ingest(ChannelEnum(data.channel), data.model_dump())
