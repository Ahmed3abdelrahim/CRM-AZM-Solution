from __future__ import annotations

import base64
import re
import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import ChannelAdapter, ChannelEnum, NormalizedMessage
from app.config import settings
from app.models.category import Category
from app.models.channel_config import ChannelConfig
from app.models.customer import Customer
from app.models.inbound_message import InboundMessage
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.repositories.scoped_repository import TenantScope
from app.schemas.channel import InboundMessageAccepted
from app.services.customer_service import ContactMethodRepository, CustomerRepository

_REFERENCE_PATTERN = re.compile(r"TKT-\d{4}-\d{6}")


def _json_safe(value: Any) -> Any:
    """`inbound_messages.raw_payload` is JSONB (data-model.md §1.25) — a real IMAP-fetched
    message's `raw` dict carries the message's raw bytes (`EmailAdapter.fetch_unseen()`), which
    has no direct JSON representation; base64-encode any `bytes` found so the insert never fails
    regardless of which adapter produced `raw`."""
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value

_CONTACT_KIND_BY_CHANNEL = {
    ChannelEnum.EMAIL: "email",
    ChannelEnum.WHATSAPP: "whatsapp",
    ChannelEnum.SMS: "phone",
    ChannelEnum.CHAT: "other",
    ChannelEnum.WEB: "other",
    ChannelEnum.PORTAL: "other",
}


class ChannelService:
    """plan.md §Service Classes — `ChannelService`. No `CurrentActor`/`require_permission` on
    `ingest()`/`poll_email()` (unlike every other bespoke service, whose methods all take
    `actor: CurrentActor` in plan.md's own signatures) — `POST /channels/inbound`'s
    `x-permission: ticket.create` is enforced by the router (app/api/routers/channels.py) against
    the API-key-derived `CurrentActor` instead, since `poll_email()`'s caller
    (`app/jobs/email_poll_job.py`) is a background job with no actor of its own, the same shape
    `categorization_job`/`sla_sweep_job` already use for system-level access.

    `_adapters` is a *class* attribute — `register_adapter()` is documented (plan.md) as "called
    once per adapter at app startup", and the ARQ worker process that runs `poll_email()` never
    imports `app/main.py`, so the registry has to be process-wide state populated by
    `register_default_adapters()` (called from both `app/main.py` and `app/jobs/worker.py`), not
    per-request instance state.
    """

    _adapters: ClassVar[dict[ChannelEnum, ChannelAdapter]] = {}

    def __init__(self, session: AsyncSession | None = None) -> None:
        # `session=None` is only valid for `register_adapter()` calls (startup-time adapter
        # registration, app/main.py / app/jobs/worker.py) — every other method requires a real
        # session and is never called on a session-less instance.
        self.session = session

    def register_adapter(self, adapter: ChannelAdapter) -> None:
        ChannelService._adapters[adapter.channel] = adapter

    # ---------------------------------------------------------------- ingest

    async def ingest(self, channel: ChannelEnum, raw: dict[str, Any]) -> InboundMessageAccepted:
        """`inbound_messages` is DB-level insert-only (data-model.md §0.3 / alembic
        `0001_initial.py`'s `INSERT_ONLY_TABLES` trigger — UPDATE is rejected outright, not just
        discouraged by convention). plan.md's "the raw payload is persisted before any further
        processing" is therefore read as "captured", not "written first and mutated later": every
        field this method could ever set (`ticket_id`, `normalized`, `processed_at`, `error`) is
        resolved in memory first, and the row is written exactly once, at the very end, in
        whichever final shape processing actually reached — success or caught failure alike."""
        adapter = self._adapters.get(channel)
        if adapter is None:
            raise ValueError(f"No channel adapter registered for {channel}")

        ticket: Ticket | None = None
        error: str | None = None
        message: NormalizedMessage | None = None
        try:
            # A Tier-D adapter's `normalize()` raises `NotImplementedError` here (FR-025 — "a
            # channel not yet built MUST be able to report that it is unavailable without
            # affecting the operation of any other channel"); caught by the same handler as every
            # other resolution failure below, so it becomes a recorded, 202-accepted
            # `inbound_messages` row with `error` set and `ticket_id` NULL, never a bare 500.
            message = adapter.normalize(raw)

            # Idempotency / redelivery: `inbound_messages` has a UNIQUE(channel, external_id)
            # constraint (data-model.md §1.25) — a webhook retry of the exact same message must
            # not create a second ticket. If this external_id was already processed, thread onto
            # the ticket it already produced instead of inserting a duplicate row.
            existing = await self.session.execute(
                select(InboundMessage).where(
                    InboundMessage.channel == channel.value, InboundMessage.external_id == message.external_id
                )
            )
            existing_row = existing.scalars().first()
            if existing_row is not None and existing_row.ticket_id is not None:
                existing_ticket = await self.session.get(Ticket, existing_row.ticket_id)
                if existing_ticket is not None:
                    await self._append_message_event(existing_ticket, message)
                    await self.session.flush()
                return InboundMessageAccepted(
                    inbound_message_id=existing_row.id, ticket_id=existing_row.ticket_id
                )

            ticket = await self._find_ticket_by_reference(message)
            config = await self._match_channel_config(message.to_identity)

            if ticket is not None:
                # FR-023b — the quoted ticket's own branch/department wins outright; a mismatch
                # against the receiving identifier's configured branch/department is recorded on
                # the timeline but never blocks the append.
                if config is not None and (
                    config.branch_id != ticket.branch_id or config.department_id != ticket.department_id
                ):
                    await self._record_scope_mismatch(ticket, config)
                await self._append_message_event(ticket, message)
            else:
                if config is not None:
                    resolved_branch_id, resolved_department_id = config.branch_id, config.department_id
                    needs_triage = False
                    default_category_id = config.default_category_id
                else:
                    resolved_branch_id = settings.SYSTEM_DEFAULT_BRANCH_ID
                    resolved_department_id = settings.SYSTEM_DEFAULT_DEPARTMENT_ID
                    needs_triage = True
                    default_category_id = None

                # Constitution/plan.md self-audit finding — a fresh TenantScope built from the
                # resolved branch/department, never the caller's own scope (the caller here is
                # typically an API-key client with no single home branch).
                resolved_scope = TenantScope(branch_id=resolved_branch_id, department_id=resolved_department_id)
                customer = await self._find_or_create_customer(resolved_scope, message)
                ticket = await self._create_ticket(
                    resolved_scope, customer, message, default_category_id, needs_triage, channel
                )
        except Exception as exc:  # noqa: BLE001 — always record the inbound message, never 500 it
            error = str(exc)
            ticket = None

        inbound = InboundMessage(
            branch_id=None,
            channel=channel.value,
            # `adapter.normalize()` itself may be what failed (Tier-D adapters, or a malformed
            # `raw`) — `raw.get("external_id")` is the same fallback the router's own
            # `NormalizedMessagePayload` always carries; a real IMAP-fetched raw dict has no such
            # key pre-parse, so a fresh UUID stands in rather than violating the NOT NULL column.
            external_id=(message.external_id if message is not None else raw.get("external_id")) or str(uuid.uuid4()),
            raw_payload=_json_safe(raw),
            # `attachments` excluded: a real IMAP-fetched message's `NormalizedAttachment.data` is
            # raw bytes, with no lossless direct JSON representation — attachment content belongs
            # on the ticket's own timeline once a real attachment-ingestion path exists (out of
            # this batch's scope), not duplicated into this JSONB debugging snapshot.
            normalized=message.model_dump(mode="json", exclude={"attachments"}) if message is not None else None,
            ticket_id=ticket.id if ticket is not None else None,
            processed_at=datetime.now(UTC),
            error=error,
        )
        self.session.add(inbound)
        await self.session.flush()

        return InboundMessageAccepted(inbound_message_id=inbound.id, ticket_id=ticket.id if ticket is not None else None)

    async def _find_ticket_by_reference(self, message: NormalizedMessage) -> Ticket | None:
        haystack = f"{message.subject or ''} {message.body}"
        match = _REFERENCE_PATTERN.search(haystack)
        if match is None:
            return None
        result = await self.session.execute(select(Ticket).where(Ticket.reference_no == match.group(0)))
        return result.scalar_one_or_none()

    async def _match_channel_config(self, to_identity: str) -> ChannelConfig | None:
        result = await self.session.execute(
            select(ChannelConfig).where(
                ChannelConfig.identifier == to_identity, ChannelConfig.is_active.is_(True)
            )
        )
        return result.scalar_one_or_none()

    async def _find_or_create_customer(self, scope: TenantScope, message: NormalizedMessage) -> Customer:
        customer_repo = CustomerRepository(self.session, scope)
        existing = await customer_repo.find_by_contact_value(message.from_identity)
        if existing is not None:
            return existing

        customer = await customer_repo.create(
            {
                "branch_id": scope.branch_id,
                "department_id": scope.department_id,
                "customer_type": "individual",
                "full_name_ar": message.from_identity,
                "full_name_en": message.from_identity,
                "national_id": None,
                "organization_name": None,
                "preferred_locale": message.locale,
                "notes": None,
                "is_active": True,
            }
        )
        contact_repo = ContactMethodRepository(self.session, scope)
        await contact_repo.create(
            {
                "customer_id": customer.id,
                "kind": _CONTACT_KIND_BY_CHANNEL[message.channel],
                "value": message.from_identity,
                "is_primary": True,
                "is_verified": False,
            }
        )
        return customer

    async def _resolve_default_category_id(self, branch_id: UUID, department_id: UUID) -> UUID:
        """Same data-driven, lowest-`sort_order` shape as `TicketService._resolve_initial_status_id`
        (Principle XI) — used only when `channel_configs.default_category_id` is unset (or there
        was no `channel_configs` match at all), since neither `NormalizedMessagePayload` nor a
        `channel_configs` miss carries any category information of its own."""
        stmt = (
            select(Category.id)
            .where(
                Category.branch_id == branch_id,
                (Category.department_id == department_id) | (Category.department_id.is_(None)),
                Category.is_active.is_(True),
            )
            .order_by(Category.sort_order.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        category_id = result.scalar_one_or_none()
        if category_id is None:
            raise ValueError(f"No category configured for branch={branch_id} department={department_id}")
        return category_id

    async def _resolve_default_priority_id(self, branch_id: UUID, department_id: UUID) -> UUID:
        """Highest `severity` number (least urgent) — a channel-created ticket has no priority
        signal of its own, so it starts at the least-urgent default rather than guessing "urgent"
        for every unclassified inbound message; an agent re-prioritizes on triage."""
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
            raise ValueError(f"No priority configured for branch={branch_id} department={department_id}")
        return priority_id

    async def _create_ticket(
        self,
        scope: TenantScope,
        customer: Customer,
        message: NormalizedMessage,
        default_category_id: UUID | None,
        needs_triage: bool,
        channel: ChannelEnum,
    ) -> Ticket:
        """Builds the `Ticket` row directly rather than going through `TicketService.create()` —
        that method's `@audited`/`@require_permission` decorators need a real `CurrentActor` whose
        `user_id` is a genuine `users.id` row (`ticket_events.actor_id`/`audit_logs.actor_id` are
        FK-constrained to `users`), and a channel-originated ticket has no such user: its actor is
        an external sender, not staff. Every write below therefore uses `actor_id=None`
        (nullable, `data-model.md` §1.17) and no `AuditLog` row is written at all — the same
        "system-level access, no actor" shape `sla_sweep_job`'s `sla_breached` events already use
        (app/services/sla_service.py `sweep_breaches`)."""
        from app.services.sla_service import SlaService  # local: avoid import cycle
        from app.services.ticket_service import (  # local: avoid import cycle
            _enqueue_categorization_job,
            generate_reference_no,
            resolve_initial_status_id,
        )

        category_id = default_category_id or await self._resolve_default_category_id(
            scope.branch_id, scope.department_id
        )
        priority_id = await self._resolve_default_priority_id(scope.branch_id, scope.department_id)
        reference_no = await generate_reference_no(self.session)
        status_id = await resolve_initial_status_id(self.session, scope.branch_id, scope.department_id)

        sla_service = SlaService(self.session, scope)
        sla_policy = await sla_service.resolve_policy(scope.branch_id, scope.department_id, category_id, priority_id)

        ticket = Ticket(
            branch_id=scope.branch_id,
            department_id=scope.department_id,
            reference_no=reference_no,
            customer_id=customer.id,
            subject=message.subject or message.body[:120],
            description=message.body,
            category_id=category_id,
            priority_id=priority_id,
            status_id=status_id,
            channel=channel.value,
            source_locale=message.locale,
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
        return ticket

    async def _append_message_event(self, ticket: Ticket, message: NormalizedMessage) -> None:
        self.session.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=None,
                event_type="reply_sent",
                body=message.body,
                visibility="customer",
                correlation_id=uuid.uuid4(),
            )
        )

    async def _record_scope_mismatch(self, ticket: Ticket, config: ChannelConfig) -> None:
        for field_name, old_value, new_value in (
            ("branch_id", ticket.branch_id, config.branch_id),
            ("department_id", ticket.department_id, config.department_id),
        ):
            if old_value != new_value:
                self.session.add(
                    TicketEvent(
                        ticket_id=ticket.id,
                        actor_id=None,
                        event_type="field_changed",
                        field_name=field_name,
                        old_value={"value": str(old_value)},
                        new_value={"value": str(new_value)},
                        reason="channel_config_scope_mismatch",
                        visibility="internal",
                        correlation_id=uuid.uuid4(),
                    )
                )

    # ---------------------------------------------------------------- poll_email

    async def poll_email(self) -> int:
        """`email_poll_job`'s body — fetches unseen mail via the registered `EmailAdapter`'s
        `fetch_unseen()` (not part of the `ChannelAdapter` protocol; polling is inherently
        channel-specific) and calls `ingest()` per message. Returns 0 (never raises) when no
        email adapter is registered or the mailbox is unconfigured/unreachable."""
        adapter = self._adapters.get(ChannelEnum.EMAIL)
        fetch_unseen = getattr(adapter, "fetch_unseen", None)
        if fetch_unseen is None:
            return 0

        raw_messages = fetch_unseen()
        count = 0
        for raw in raw_messages:
            await self.ingest(ChannelEnum.EMAIL, raw)
            count += 1
        return count


def register_default_adapters() -> None:
    """Called once at process startup — both `app/main.py` (the API process) and
    `app/jobs/worker.py` (the ARQ worker process, a separate Python process that never imports
    `app/main.py`) call this so `ChannelService._adapters` is populated in either process."""
    from app.channels.chat_adapter import ChatAdapter
    from app.channels.email_adapter import EmailAdapter
    from app.channels.sms_adapter import SmsAdapter
    from app.channels.whatsapp_adapter import WhatsappAdapter

    registrar = ChannelService()
    for adapter in (EmailAdapter(), WhatsappAdapter(), SmsAdapter(), ChatAdapter()):
        registrar.register_adapter(adapter)
