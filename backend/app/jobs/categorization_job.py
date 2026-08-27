"""ARQ job body, enqueued by `TicketService.create` (app/services/ticket_service.py,
`_enqueue_categorization_job`) without being awaited, so AI latency never delays the ticket-create
response (FR-049).

Batch 4h scope only: calls `AiService.categorize`, which writes `ai_suggested_category_id`/
`ai_category_confidence` (or leaves both `NULL` on fallback). Batch 4f's `AssignmentService`
(round-robin auto-assignment, meant to run immediately after categorization per plan.md
§Service Classes) is explicitly out of scope for this run — this job does not call it. Batch 4f
adds that call here when it lands; until then, a categorized ticket is left unassigned rather than
silently auto-assigned by code this run didn't build."""

from __future__ import annotations

from uuid import UUID

from app.db import async_session_factory
from app.repositories.scoped_repository import TenantScope
from app.services.ai_service import AiService


async def categorization_job(ctx: dict, ticket_id: UUID) -> None:
    async with async_session_factory() as session:
        # A background job has no CurrentActor/tenant scope of its own; cross_branch=True bypasses
        # ScopedRepository's branch/department predicate entirely (scoped_repository.py) so the
        # job can reach the one ticket it was enqueued for regardless of which tenant it belongs
        # to — the same deliberate use of cross_branch as system-level access documented for
        # cross-branch reporting.
        service = AiService(session, TenantScope(branch_id=None, department_id=None, cross_branch=True))
        await service.categorize(ticket_id)
