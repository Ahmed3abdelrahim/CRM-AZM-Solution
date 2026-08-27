"""ARQ job (`app/jobs/worker.py`'s `cron_jobs`) — runs `ChannelService.poll_email()` on its own
schedule, per PLAN.md F03 / Batch 4i (T123). Registers the default channel adapters on first run
in this worker process (see `app/services/channel_service.py::register_default_adapters` — the
worker never imports `app/main.py`, so this is this process's own registration point, mirroring
`app/jobs/worker.py`'s `on_startup` hook for the same reason)."""

from __future__ import annotations

from app.db import async_session_factory
from app.services.channel_service import ChannelService


async def email_poll_job(ctx: dict) -> int:
    async with async_session_factory() as session:
        service = ChannelService(session)
        count = await service.poll_email()
        await session.commit()
        return count
