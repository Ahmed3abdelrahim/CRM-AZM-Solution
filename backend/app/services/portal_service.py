from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import ValidationError
from app.models.category import Category
from app.models.customer import ContactMethod, Customer
from app.models.kb_article import KbArticle
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.repositories.scoped_repository import TenantScope
from app.schemas.portal import PortalTicketSubmit, PortalTicketView
from app.schemas.ticket import TicketEvent as TicketEventSchema
from app.services.customer_service import ContactMethodRepository, CustomerRepository

_ARABIC_BLOCK = range(0x0600, 0x0700)


def _detect_locale(*texts: str | None) -> str:
    for text in texts:
        for char in text or "":
            if ord(char) in _ARABIC_BLOCK:
                return "ar"
    return "en"


class PortalService:
    """plan.md §Service Classes — `PortalService`. Unauthenticated — no `CurrentActor`/
    `require_permission` on any method (every one of `contracts/openapi.yaml`'s `/portal/*` paths
    is `security: []`). Tickets are created the same way `ChannelService._create_ticket` does
    (`generate_reference_no`/`resolve_initial_status_id`, `app/services/ticket_service.py`, not
    `TicketService.create()` itself) for the identical reason: no real `users.id` actor exists
    for a customer-submitted ticket, and `ticket_events.actor_id`/`audit_logs.actor_id` are
    FK-constrained to `users`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit_ticket(self, data: PortalTicketSubmit) -> str:
        """FR-052. Branch is always `category_id`'s own branch (categories are S2-scoped to
        exactly one branch); department is the category's own department, else the same
        system-default + `needs_triage` fallback `ChannelService` uses (plan.md §Service Classes
        `PortalService.submit_ticket`)."""
        from app.services.sla_service import SlaService  # local: avoid import cycle
        from app.services.ticket_service import (  # local: avoid import cycle
            _enqueue_categorization_job,
            generate_reference_no,
            resolve_initial_status_id,
        )

        category = await self.session.get(Category, data.category_id)
        if category is None or not category.is_active:
            raise ValidationError(
                "التصنيف المحدد غير صالح",
                "The selected category is invalid",
            )

        branch_id = category.branch_id
        needs_triage = category.department_id is None
        department_id = category.department_id or settings.SYSTEM_DEFAULT_DEPARTMENT_ID
        scope = TenantScope(branch_id=branch_id, department_id=department_id)

        locale = _detect_locale(data.subject, data.description)
        customer = await self._find_or_create_customer(scope, data, locale)

        priority_id = await self._resolve_default_priority_id(branch_id, department_id)
        reference_no = await generate_reference_no(self.session)
        status_id = await resolve_initial_status_id(self.session, branch_id, department_id)

        sla_service = SlaService(self.session, scope)
        sla_policy = await sla_service.resolve_policy(branch_id, department_id, category.id, priority_id)

        ticket = Ticket(
            branch_id=branch_id,
            department_id=department_id,
            reference_no=reference_no,
            customer_id=customer.id,
            subject=data.subject,
            description=data.description,
            category_id=category.id,
            priority_id=priority_id,
            status_id=status_id,
            channel="portal",
            source_locale=locale,
            sla_policy_id=sla_policy.id if sla_policy is not None else None,
            needs_triage=needs_triage,
        )
        self.session.add(ticket)
        await self.session.flush()

        self.session.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=None,
                event_type="created",
                visibility="customer",
                correlation_id=uuid.uuid4(),
            )
        )
        await self.session.flush()

        _enqueue_categorization_job(ticket.id)
        return ticket.reference_no

    async def _find_or_create_customer(
        self, scope: TenantScope, data: PortalTicketSubmit, locale: str
    ) -> Customer:
        customer_repo = CustomerRepository(self.session, scope)
        existing = await customer_repo.find_by_contact_value(data.contact_value)
        if existing is not None:
            return existing

        customer = await customer_repo.create(
            {
                "branch_id": scope.branch_id,
                "department_id": scope.department_id,
                "customer_type": "individual",
                "full_name_ar": data.full_name,
                "full_name_en": data.full_name,
                "national_id": None,
                "organization_name": None,
                "preferred_locale": locale,
                "notes": None,
                "is_active": True,
            }
        )
        contact_repo = ContactMethodRepository(self.session, scope)
        await contact_repo.create(
            {
                "customer_id": customer.id,
                "kind": data.contact_kind,
                "value": data.contact_value,
                "is_primary": True,
                "is_verified": False,
            }
        )
        return customer

    async def _resolve_default_priority_id(self, branch_id, department_id):
        stmt = (
            select(Priority.id)
            .where(
                Priority.branch_id == branch_id,
                (Priority.department_id == department_id) | (Priority.department_id.is_(None)),
            )
            .order_by(Priority.severity.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        priority_id = result.scalar_one_or_none()
        if priority_id is None:
            raise ValidationError(
                "لا توجد أولوية معرفة لهذا الفرع",
                "No priority is configured for this branch",
            )
        return priority_id

    # ---------------------------------------------------------------- tracking

    async def _resolve_ticket_and_customer(
        self, reference_no: str, contact_value: str
    ) -> tuple[Ticket, Customer] | None:
        """`None` on any mismatch — unknown reference OR wrong contact — so the router returns an
        identical 404 either way (FR-053); no branching on "which reason" past this method."""
        result = await self.session.execute(select(Ticket).where(Ticket.reference_no == reference_no))
        ticket = result.scalar_one_or_none()
        if ticket is None:
            return None

        customer = await self.session.get(Customer, ticket.customer_id)
        if customer is None:
            return None

        contact_result = await self.session.execute(
            select(ContactMethod).where(
                ContactMethod.customer_id == customer.id, ContactMethod.value.ilike(contact_value)
            )
        )
        if contact_result.scalars().first() is None:
            return None
        return ticket, customer

    async def _customer_visible_events(self, ticket_id) -> list[TicketEventSchema]:
        """FR-054 — never includes `visibility="internal"` entries."""
        result = await self.session.execute(
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id, TicketEvent.visibility == "customer")
            .order_by(TicketEvent.created_at)
        )
        return [TicketEventSchema.model_validate(event) for event in result.scalars().all()]

    def _to_view(self, ticket: Ticket, events: list[TicketEventSchema]) -> PortalTicketView:
        return PortalTicketView(
            reference_no=ticket.reference_no,
            subject=ticket.subject,
            status_id=ticket.status_id,
            created_at=ticket.created_at,
            events=events,
        )

    async def track_ticket(self, reference_no: str, contact_value: str) -> PortalTicketView | None:
        resolved = await self._resolve_ticket_and_customer(reference_no, contact_value)
        if resolved is None:
            return None
        ticket, _customer = resolved
        events = await self._customer_visible_events(ticket.id)
        return self._to_view(ticket, events)

    async def get_history(self, reference_no: str, contact_value: str) -> list[PortalTicketView] | None:
        """FR-054 — own tickets only, resolved via the same reference+contact pairing as
        `track_ticket`."""
        resolved = await self._resolve_ticket_and_customer(reference_no, contact_value)
        if resolved is None:
            return None
        _ticket, customer = resolved

        result = await self.session.execute(
            select(Ticket).where(Ticket.customer_id == customer.id).order_by(Ticket.created_at.desc())
        )
        tickets = list(result.scalars().all())
        views = []
        for ticket in tickets:
            events = await self._customer_visible_events(ticket.id)
            views.append(self._to_view(ticket, events))
        return views

    # ---------------------------------------------------------------- KB (FR-055)

    async def list_published_kb_articles(self) -> list[KbArticle]:
        result = await self.session.execute(
            select(KbArticle).where(KbArticle.is_published.is_(True)).order_by(KbArticle.branch_id, KbArticle.slug)
        )
        return list(result.scalars().all())

    async def get_published_kb_article_by_slug(self, slug: str) -> KbArticle | None:
        """`slug` is unique only per-branch (`uq_kb_articles_branch_slug`, data-model.md §1.21),
        not globally — `contracts/openapi.yaml`'s `/portal/kb/articles/{slug}` takes no branch
        qualifier at all, so a slug shared by two branches' catalogs (the seeded demo data does
        this deliberately) resolves to the first match in a stable, deterministic order rather
        than being ambiguous."""
        result = await self.session.execute(
            select(KbArticle)
            .where(KbArticle.slug == slug, KbArticle.is_published.is_(True))
            .order_by(KbArticle.branch_id)
            .limit(1)
        )
        return result.scalars().first()
