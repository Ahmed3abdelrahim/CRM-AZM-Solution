"""ARQ cron job (`app/jobs/worker.py`'s `cron_jobs`) — runs `SlaService.sweep_breaches()` every
5 minutes (PLAN.md F05). Idempotent by construction: `sweep_breaches` only writes an
`sla_breached` event when none already exists yet for a ticket's current target, so running the
sweep twice in a row produces zero additional events on the second run (F05 acceptance #4)."""

from __future__ import annotations

from app.db import async_session_factory
from app.repositories.scoped_repository import TenantScope
from app.services.sla_service import SlaService


async def sla_sweep_job(ctx: dict) -> int:
    async with async_session_factory() as session:
        # A background job has no CurrentActor/tenant scope of its own — cross_branch=True
        # bypasses ScopedRepository's branch/department predicate entirely, the same deliberate
        # system-level access categorization_job (Batch 4h) uses to reach a ticket regardless of
        # tenant. sweep_breaches() itself does not go through TicketRepository at all (it spans
        # every branch/department in one pass), but the scope is still required by SlaService's
        # constructor shape shared with request-scoped callers.
        service = SlaService(session, TenantScope(branch_id=None, department_id=None, cross_branch=True))
        count = await service.sweep_breaches()
        await session.commit()
        return count
