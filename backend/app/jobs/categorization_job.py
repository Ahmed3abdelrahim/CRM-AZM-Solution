"""ARQ job body, enqueued by `TicketService.create` (app/services/ticket_service.py,
`_enqueue_categorization_job`) without being awaited, so AI latency never delays the ticket-create
response (FR-049).

Calls `AiService.categorize` (Batch 4h), which writes `ai_suggested_category_id`/
`ai_category_confidence` (or leaves both `NULL` on fallback), then `AssignmentService.
auto_assign_ticket` (Batch 4f, T092/T096) so a newly created ticket is round-robin-assigned right
after categorization completes — per plan.md §Service Classes: `AssignmentService.auto_assign_ticket`
is called only here, never synchronously from `TicketService.create`, so a ticket is never
double-assigned against this job's own call."""

from __future__ import annotations

from uuid import UUID

from app.db import async_session_factory
from app.repositories.scoped_repository import TenantScope
from app.services.ai_service import AiService
from app.services.assignment_service import AssignmentService


async def categorization_job(ctx: dict, ticket_id: UUID) -> None:
    async with async_session_factory() as session:
        # A background job has no CurrentActor/tenant scope of its own; cross_branch=True bypasses
        # ScopedRepository's branch/department predicate entirely (scoped_repository.py) so the
        # job can reach the one ticket it was enqueued for regardless of which tenant it belongs
        # to — the same deliberate use of cross_branch as system-level access documented for
        # cross-branch reporting.
        service = AiService(session, TenantScope(branch_id=None, department_id=None, cross_branch=True))
        await service.categorize(ticket_id)  # commits internally (app/services/ai_service.py)

        await AssignmentService(session).auto_assign_ticket(ticket_id)
        await session.commit()
