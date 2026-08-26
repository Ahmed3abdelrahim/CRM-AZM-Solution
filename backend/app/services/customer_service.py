from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audited
from app.core.errors import NotFoundError, ValidationError
from app.core.permissions import CurrentActor, require_permission
from app.core.storage import put_object
from app.models.attachment import Attachment
from app.models.customer import ContactMethod, Customer
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.repositories.scoped_repository import ScopedRepository, ScopingMode, TenantScope
from app.schemas.customer import ContactMethodCreate, CustomerCreate, CustomerHistory, CustomerUpdate


class CustomerRepository(ScopedRepository[Customer]):
    model = Customer
    scoping_mode = ScopingMode.S1_FULL
    has_soft_delete = True

    async def search(self, q: str | None, limit: int = 50, offset: int = 0) -> list[Customer]:
        """FR-012 — matches `full_name_ar`/`full_name_en`/`organization_name`/every
        `contact_methods.value`. Filtering uses `ILIKE '%q%'`, which the `gin_trgm_ops` indexes
        on those columns (data-model.md §1.10/§1.11) accelerate for arbitrary substrings — the
        `%` similarity operator's default 0.3 threshold would reject a short query against a
        much longer name/value, which the F01 acceptance criterion (a bare 3-character Arabic
        substring) requires to match. `similarity()` is used only to rank matches, never to
        filter them out."""
        stmt = self._scoped_select()
        if not q:
            return list(
                (await self.session.execute(stmt.order_by(self.model.full_name_ar).limit(limit).offset(offset)))
                .scalars()
                .all()
            )

        pattern = f"%{q}%"
        matching_customer_ids = select(ContactMethod.customer_id).where(ContactMethod.value.ilike(pattern))
        stmt = stmt.where(
            or_(
                Customer.full_name_ar.ilike(pattern),
                Customer.full_name_en.ilike(pattern),
                Customer.organization_name.ilike(pattern),
                Customer.id.in_(matching_customer_ids),
            )
        )
        best_similarity = func.greatest(
            func.similarity(func.coalesce(Customer.full_name_ar, ""), q),
            func.similarity(func.coalesce(Customer.full_name_en, ""), q),
            func.similarity(func.coalesce(Customer.organization_name, ""), q),
        )
        stmt = stmt.order_by(best_similarity.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ContactMethodRepository(ScopedRepository[ContactMethod]):
    model = ContactMethod
    scoping_mode = ScopingMode.S4_TRANSITIVE
    parent_model = Customer
    parent_fk_column = "customer_id"


class CustomerService:
    """plan.md §Service Classes — `CustomerService`. Not an `AdminCrudService` subclass: F01's
    rules (contact-method validation on create, the history merge, attachment upload) are all
    bespoke, so this class wires `require_permission`/`audited` itself rather than inheriting
    the Generic CRUD Pattern (which assumes a single schema-shaped `create`)."""

    def __init__(self, session: AsyncSession, scope: TenantScope) -> None:
        self.session = session
        self.scope = scope
        self.repository = CustomerRepository(session, scope)
        self.contact_method_repository = ContactMethodRepository(session, scope)

    def _not_found(self, id: UUID) -> NotFoundError:
        return NotFoundError(f"العميل غير موجود: {id}", f"Customer not found: {id}")

    @require_permission("customer.read")
    async def search(self, actor: CurrentActor, q: str | None, limit: int = 50, offset: int = 0) -> list[Customer]:
        return await self.repository.search(q, limit=limit, offset=offset)

    @require_permission("customer.read")
    async def get(self, actor: CurrentActor, id: UUID) -> Customer:
        customer = await self.repository.get(id)
        if customer is None:
            raise self._not_found(id)
        return customer

    @require_permission("customer.create")
    async def create(self, actor: CurrentActor, data: CustomerCreate) -> Customer:
        primary_count = sum(1 for cm in data.contact_methods if cm.is_primary)
        if not data.contact_methods or primary_count != 1:
            raise ValidationError(
                "يجب إدخال وسيلة اتصال واحدة على الأقل، مع تحديد واحدة فقط كأساسية",
                "At least one contact method is required, with exactly one marked as primary",
            )
        return await self._create_audited(actor, None, data)

    @audited("customer", "create")
    async def _create_audited(self, actor: CurrentActor, id: None, data: CustomerCreate) -> Customer:
        values = data.model_dump(exclude={"contact_methods"})
        values["created_by"] = actor.user_id
        customer = await self.repository.create(values)
        for contact_method in data.contact_methods:
            await self.contact_method_repository.create(
                {
                    "customer_id": customer.id,
                    "kind": contact_method.kind,
                    "value": contact_method.value,
                    "is_primary": contact_method.is_primary,
                    "created_by": actor.user_id,
                }
            )
        return customer

    @require_permission("customer.create")
    @audited("customer", "update")
    async def update(self, actor: CurrentActor, id: UUID, data: CustomerUpdate) -> Customer:
        existing = await self.repository.get(id)
        if existing is None:
            raise self._not_found(id)
        values = data.model_dump(exclude_unset=True)
        values["updated_by"] = actor.user_id
        return await self.repository.update(id, values)

    @require_permission("customer.delete")
    @audited("customer", "deactivate")
    async def deactivate(self, actor: CurrentActor, id: UUID) -> Customer:
        existing = await self.repository.get(id)
        if existing is None:
            raise self._not_found(id)
        return await self.repository.deactivate(id)

    @require_permission("customer.read")
    async def get_history(self, actor: CurrentActor, id: UUID) -> CustomerHistory:
        """FR-014 — merges every ticket owned by this customer with every event on those
        tickets, each list sorted chronologically. Reads `tickets`/`ticket_events` directly
        (rather than via a `ScopedRepository[Ticket]`, which Batch 4d's `ticket_repository.py`
        introduces) — scoping is still enforced, just inline: `customer` above is only reachable
        once already resolved through `CustomerRepository`'s own S1 scope, and every ticket read
        here is additionally constrained to that exact customer/branch/department triple."""
        customer = await self.repository.get(id)
        if customer is None:
            raise self._not_found(id)

        tickets_result = await self.session.execute(
            select(Ticket)
            .where(
                Ticket.customer_id == customer.id,
                Ticket.branch_id == customer.branch_id,
                Ticket.department_id == customer.department_id,
            )
            .order_by(Ticket.created_at)
        )
        tickets = list(tickets_result.scalars().all())

        events: list[TicketEvent] = []
        ticket_ids = [ticket.id for ticket in tickets]
        if ticket_ids:
            events_result = await self.session.execute(
                select(TicketEvent).where(TicketEvent.ticket_id.in_(ticket_ids)).order_by(TicketEvent.created_at)
            )
            events = list(events_result.scalars().all())

        return CustomerHistory(tickets=tickets, events=events)

    @require_permission("customer.read")
    async def list_contact_methods(self, actor: CurrentActor, customer_id: UUID) -> list[ContactMethod]:
        customer = await self.repository.get(customer_id)
        if customer is None:
            raise self._not_found(customer_id)
        return await self.contact_method_repository.list(filters={"customer_id": customer_id}, limit=200)

    @require_permission("customer.create")
    async def add_contact_method(
        self, actor: CurrentActor, customer_id: UUID, data: ContactMethodCreate
    ) -> ContactMethod:
        customer = await self.repository.get(customer_id)
        if customer is None:
            raise self._not_found(customer_id)
        return await self._add_contact_method_audited(actor, None, customer_id, data)

    @audited("contact_method", "create")
    async def _add_contact_method_audited(
        self, actor: CurrentActor, id: None, customer_id: UUID, data: ContactMethodCreate
    ) -> ContactMethod:
        if data.is_primary:
            # Satisfies contact_methods' one-primary-per-customer partial unique index
            # (data-model.md §1.11) when a caller adds a new primary contact.
            existing_primary = await self.session.execute(
                select(ContactMethod).where(
                    ContactMethod.customer_id == customer_id, ContactMethod.is_primary.is_(True)
                )
            )
            for row in existing_primary.scalars().all():
                row.is_primary = False
            await self.session.flush()

        return await self.contact_method_repository.create(
            {
                "customer_id": customer_id,
                "kind": data.kind,
                "value": data.value,
                "is_primary": data.is_primary,
                "created_by": actor.user_id,
            }
        )

    @require_permission("customer.create")
    async def add_attachment(self, actor: CurrentActor, customer_id: UUID, file: UploadFile) -> Attachment:
        customer = await self.repository.get(customer_id)
        if customer is None:
            raise self._not_found(customer_id)
        return await self._add_attachment_audited(actor, None, customer, file)

    @audited("attachment", "create")
    async def _add_attachment_audited(
        self, actor: CurrentActor, id: None, customer: Customer, file: UploadFile
    ) -> Attachment:
        data = await file.read()
        content_type = file.content_type or "application/octet-stream"
        storage_key = await asyncio.to_thread(put_object, data, content_type, prefix=f"customers/{customer.id}")

        attachment = Attachment(
            branch_id=customer.branch_id,
            department_id=customer.department_id,
            customer_id=customer.id,
            filename=file.filename or "attachment",
            content_type=content_type,
            size_bytes=len(data),
            storage_key=storage_key,
            uploaded_by=actor.user_id,
            created_by=actor.user_id,
        )
        self.session.add(attachment)
        await self.session.flush()
        return attachment
