from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.jobs.categorization_job import categorization_job
from app.jobs.sla_sweep_job import sla_sweep_job


class WorkerSettings:
    """ARQ worker entry point (`arq app.jobs.worker.WorkerSettings`). `categorization_job` is
    enqueued on demand, by name, from `TicketService.create` (Batch 4h). `sla_sweep_job` (Batch
    4f, T094/T095) runs on its own schedule instead — every 5 minutes, per PLAN.md F05 — via
    ARQ's `cron_jobs`, not `functions`. `email_poll_job` (Batch 4i) is registered here by the
    batch that implements it."""

    functions = [categorization_job]
    cron_jobs = [cron(sla_sweep_job, minute=set(range(0, 60, 5)))]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
