from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.jobs.categorization_job import categorization_job
from app.jobs.email_poll_job import email_poll_job
from app.jobs.sla_sweep_job import sla_sweep_job
from app.services.channel_service import register_default_adapters


async def _on_startup(ctx: dict) -> None:
    """This worker process never imports `app/main.py`, so `ChannelService`'s adapter registry
    (a process-wide class attribute) needs its own registration point here — otherwise
    `email_poll_job` would find no `EmailAdapter` registered and silently poll nothing."""
    register_default_adapters()


class WorkerSettings:
    """ARQ worker entry point (`arq app.jobs.worker.WorkerSettings`). `categorization_job` is
    enqueued on demand, by name, from `TicketService.create` (Batch 4h). `sla_sweep_job` (Batch
    4f, T094/T095) and `email_poll_job` (Batch 4i, T123) each run on their own schedule instead —
    every 5 minutes, per PLAN.md F05/F03 — via ARQ's `cron_jobs`, not `functions`."""

    functions = [categorization_job]
    cron_jobs = [
        cron(sla_sweep_job, minute=set(range(0, 60, 5))),
        cron(email_poll_job, minute=set(range(0, 60, 5))),
    ]
    on_startup = _on_startup
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
