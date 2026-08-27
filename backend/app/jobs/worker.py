from arq.connections import RedisSettings

from app.config import settings
from app.jobs.categorization_job import categorization_job


class WorkerSettings:
    """ARQ worker entry point (`arq app.jobs.worker.WorkerSettings`). `email_poll_job`/
    `sla_sweep_job` (Batches 4f/4i) are registered here by the batches that implement them; the
    placeholder `noop` this file used to carry (Batch 4a, before any real job existed) is removed
    now that `categorization_job` (Batch 4h) fills that role."""

    functions = [categorization_job]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
