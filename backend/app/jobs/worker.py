from arq.connections import RedisSettings

from app.config import settings


async def noop(ctx: dict) -> None:
    """Placeholder so ARQ's Worker has at least one registered function to start with
    (arq.worker.Worker requires a non-empty functions/cron_jobs list). Real jobs
    (email_poll_job/categorization_job/sla_sweep_job) are registered here by the batches that
    implement them (PLAN.md §6 4f/4h); this function is removed once one exists."""
    return None


class WorkerSettings:
    """ARQ worker entry point (`arq app.jobs.worker.WorkerSettings`)."""

    functions = [noop]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
