from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import categorization, suggested_reply, summary
from app.ai.litellm_wrapper import LiteLlmWrapper, LlmCapability
from app.config import settings
from app.core.audit import audited
from app.core.errors import NotFoundError, ValidationError
from app.core.permissions import CurrentActor, require_permission
from app.models.category import Category
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.repositories.scoped_repository import TenantScope
from app.repositories.ticket_repository import TicketRepository
from app.schemas.ai import AiSuggestedReplyResponse, AiSummaryResponse, BenchmarkResult
from app.schemas.kb_article import KbSearchResult
from app.services.kb_service import KbService
from app.services.ticket_service import attach_sla_placeholders

logger = structlog.get_logger(__name__)

_GOLDEN_SET_PATH = Path(__file__).resolve().parents[2] / "tests" / "golden" / "bilingual_tickets.json"

_wrapper = LiteLlmWrapper(
    api_base=settings.LITELLM_API_BASE,
    api_key=settings.LITELLM_API_KEY,
    model_chat=settings.LITELLM_MODEL_CHAT,
    model_classify=settings.LITELLM_MODEL_CLASSIFY,
    timeout_s=settings.LITELLM_TIMEOUT_SECONDS,
    max_retries=settings.LITELLM_MAX_RETRIES,
)


class AiService:
    """plan.md §Service Classes — `AiService`. Every method wraps `LiteLlmWrapper.complete()`
    (never raises itself, since the wrapper never raises); `suggest_solution` is meant to wrap
    `KbService.search()` instead (Batch 4g), which does not exist yet in this run — see that
    method's own docstring for the interim fallback-only behavior."""

    def __init__(self, session: AsyncSession, scope: TenantScope) -> None:
        self.session = session
        self.scope = scope
        self.repository = TicketRepository(session, scope)

    def _not_found(self, id: UUID) -> NotFoundError:
        return NotFoundError(f"التذكرة غير موجودة: {id}", f"Ticket not found: {id}")

    async def _get_ticket(self, id: UUID) -> Ticket:
        ticket = await self.repository.get(id)
        if ticket is None:
            raise self._not_found(id)
        return ticket

    @require_permission("ticket.read")
    async def summarize(self, actor: CurrentActor, ticket_id: UUID) -> AiSummaryResponse:
        ticket = await self._get_ticket(ticket_id)
        prompt = summary.build_prompt(ticket.subject, ticket.description, ticket.source_locale)
        result = await _wrapper.complete(
            LlmCapability.SUMMARIZE, prompt, summary.PROMPT_VERSION, ticket.id, actor.correlation_id
        )
        if result.fallback_used or not result.text:
            return AiSummaryResponse(summary=summary.fallback_summary(ticket.description), fallback_used=True)
        return AiSummaryResponse(summary=result.text.strip(), fallback_used=False)

    @require_permission("ticket.read")
    async def suggest_reply(self, actor: CurrentActor, ticket_id: UUID) -> AiSuggestedReplyResponse:
        ticket = await self._get_ticket(ticket_id)
        prompt = suggested_reply.build_prompt(ticket.subject, ticket.description, ticket.source_locale)
        result = await _wrapper.complete(
            LlmCapability.SUGGEST_REPLY,
            prompt,
            suggested_reply.PROMPT_VERSION,
            ticket.id,
            actor.correlation_id,
        )
        if result.fallback_used or not result.text:
            return AiSuggestedReplyResponse(draft=suggested_reply.FALLBACK_DRAFT, fallback_used=True)
        return AiSuggestedReplyResponse(draft=result.text.strip(), fallback_used=False)

    @require_permission("ticket.read")
    async def suggest_solution(self, actor: CurrentActor, ticket_id: UUID) -> list[KbSearchResult]:
        """FR-047 — top 3 KB articles from `KbService.search()` (Batch 4g) over
        subject+description. `KbService.search()` never raises (it degrades to lexical-only, or
        to an empty result, on its own) — the `except` below exists only for a permission gap
        between `ticket.read` and `kb_article.read` (data-model.md §5.1 grants both to the same
        three roles, so this should never actually trigger), not for AI/embedding failures."""

        ticket = await self._get_ticket(ticket_id)
        kb_service = KbService(self.session, self.scope)
        query = f"{ticket.subject} {ticket.description}"
        try:
            return await kb_service.search(actor, query, limit=3)
        except Exception as exc:  # noqa: BLE001 — FR-047's fallback is an empty list, never an error
            logger.warning("suggest_solution_failed", ticket_id=str(ticket_id), error=str(exc))
            return []

    async def _active_categories(self, ticket: Ticket) -> list[categorization.CategoryOption]:
        stmt = select(Category).where(
            Category.branch_id == ticket.branch_id,
            Category.is_active.is_(True),
            (Category.department_id == ticket.department_id) | (Category.department_id.is_(None)),
        )
        result = await self.session.execute(stmt)
        return [(str(category.id), category.label_ar, category.label_en) for category in result.scalars().all()]

    async def categorize(self, ticket_id: UUID) -> None:
        """`categorization_job`'s body (app/jobs/categorization_job.py) — no `CurrentActor`, runs
        as a background ARQ job, so it carries no `@require_permission` (plan.md's own signature
        for this method omits `actor` for the same reason). Writes `ai_suggested_category_id`/
        `ai_category_confidence` directly and NEVER `category_id` (FR-044) — on any fallback or
        unparseable model output, leaves both `NULL` (FR-049)."""

        ticket = await self.repository.get(ticket_id)
        if ticket is None:
            return
        options = await self._active_categories(ticket)
        prompt = categorization.build_prompt(ticket.subject, ticket.description, ticket.source_locale, options)
        result = await _wrapper.complete(
            LlmCapability.CATEGORIZE, prompt, categorization.PROMPT_VERSION, ticket.id, uuid4()
        )
        category_key, confidence = (None, None)
        if not result.fallback_used:
            category_key, confidence = categorization.parse_response(result.text, options)
        ticket.ai_suggested_category_id = UUID(category_key) if category_key else None
        ticket.ai_category_confidence = confidence
        await self.session.commit()

    @require_permission("ticket.create")
    async def apply_categorization_decision(
        self,
        actor: CurrentActor,
        ticket_id: UUID,
        accepted: bool,
        override_category_id: UUID | None,
    ) -> Ticket:
        return await self._apply_categorization_decision_audited(
            actor, ticket_id, accepted, override_category_id
        )

    @audited("ticket", "apply_categorization_decision")
    async def _apply_categorization_decision_audited(
        self,
        actor: CurrentActor,
        id: UUID,
        accepted: bool,
        override_category_id: UUID | None,
    ) -> Ticket:
        """FR-044 — accepting writes the ticket's real `category_id` from the AI suggestion;
        overriding requires an explicit `override_category_id` instead. Either way, an
        `ai_suggestion_applied` event records the suggestion + confidence that was offered,
        alongside the decision actually taken."""

        ticket = await self._get_ticket(id)
        suggested_category_id = ticket.ai_suggested_category_id
        confidence = ticket.ai_category_confidence

        if accepted:
            if suggested_category_id is None:
                raise ValidationError(
                    "لا يوجد تصنيف مقترح بالذكاء الاصطناعي لهذه التذكرة",
                    "This ticket has no AI-suggested category to accept",
                )
            new_category_id = suggested_category_id
        else:
            if override_category_id is None:
                raise ValidationError(
                    "يجب تحديد تصنيف بديل عند رفض الاقتراح",
                    "override_category_id is required when accepted is false",
                )
            new_category_id = override_category_id

        ticket.category_id = new_category_id
        ticket.updated_by = actor.user_id
        self.session.add(
            TicketEvent(
                ticket_id=id,
                actor_id=actor.user_id,
                event_type="ai_suggestion_applied",
                old_value={
                    "suggested_category_id": str(suggested_category_id) if suggested_category_id else None,
                    "confidence": float(confidence) if confidence is not None else None,
                },
                new_value={"category_id": str(new_category_id), "accepted": accepted},
                visibility="internal",
                correlation_id=actor.correlation_id,
                created_by=actor.user_id,
            )
        )
        await self.session.flush()
        return attach_sla_placeholders(ticket)

    @require_permission("admin.config")
    async def run_categorization_benchmark(self, actor: CurrentActor) -> BenchmarkResult:
        """FR-050 — scores `tests/golden/bilingual_tickets.json`'s fixed bilingual set. The golden
        set carries its own self-contained category taxonomy (not the DB's live categories) so
        the score is reproducible independent of any environment's seed data."""

        data = json.loads(_GOLDEN_SET_PATH.read_text(encoding="utf-8"))
        options: list[categorization.CategoryOption] = [
            (category["key"], category["label_ar"], category["label_en"]) for category in data["categories"]
        ]
        tickets = data["tickets"]

        correct = 0
        for item in tickets:
            prompt = categorization.build_prompt(
                item["subject"], item["description"], item["source_locale"], options
            )
            result = await _wrapper.complete(
                LlmCapability.CATEGORIZE, prompt, categorization.PROMPT_VERSION, None, actor.correlation_id
            )
            predicted_key = None
            if not result.fallback_used:
                predicted_key, _ = categorization.parse_response(result.text, options)
            if predicted_key == item["expected_category_key"]:
                correct += 1

        scored_count = len(tickets)
        accuracy = (correct / scored_count) if scored_count else 0.0
        return BenchmarkResult(scored_count=scored_count, accuracy=accuracy)
