"""Pause accounting shifts the deadline by exactly the paused duration; business-hours policies
don't accrue outside the branch's configured hours/timezone; `sweep_breaches()` run twice writes
exactly one `sla_breached` event per ticket/target; an SLA override with an already-past
recomputed deadline is permitted and produces a breach (Testing Proportionality — SLA
computation; also this batch's own gate, PLAN.md §6).

Requires a live Postgres reachable via DATABASE_URL, migrated to head — same as
test_ticket_transitions.py (DEBT.md D03: no testcontainers this sprint)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.permissions import CurrentActor
from app.db import async_session_factory
from app.models.branch import Branch
from app.models.category import Category
from app.models.customer import Customer
from app.models.department import Department
from app.models.priority import Priority
from app.models.sla_policy import SlaPolicy
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.ticket_status import TicketStatus
from app.models.user import User
from app.repositories.scoped_repository import TenantScope
from app.services.sla_service import SlaService


@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session
        await session.rollback()


async def _make_branch_department(session, *, timezone="UTC", business_hours=None):
    branch = Branch(
        code=f"seed-{uuid.uuid4().hex[:8]}",
        label_ar="فرع تجريبي",
        label_en="Seed branch",
        timezone=timezone,
        business_hours=business_hours or {},
    )
    session.add(branch)
    await session.flush()

    department = Department(
        branch_id=branch.id, code=f"dept-{uuid.uuid4().hex[:6]}", label_ar="قسم", label_en="Department"
    )
    session.add(department)
    await session.flush()
    return branch, department


async def _make_ticket(
    session,
    branch,
    department,
    *,
    created_at: datetime,
    sla_policy: SlaPolicy,
    sla_paused_ms: int = 0,
    priority_severity: int = 2,
    is_terminal: bool = False,
):
    category = Category(branch_id=branch.id, label_ar="تصنيف", label_en="Category")
    priority = Priority(
        branch_id=branch.id, code=f"p{priority_severity}", label_ar="أولوية", label_en="Priority",
        severity=priority_severity, color="#ff0000",
    )
    customer = Customer(
        branch_id=branch.id,
        department_id=department.id,
        customer_type="individual",
        full_name_ar="عميل تجريبي",
        preferred_locale="ar",
    )
    status = TicketStatus(
        branch_id=branch.id, code=f"status-{uuid.uuid4().hex[:6]}", label_ar="حالة", label_en="Status",
        is_terminal=is_terminal, pauses_sla=False, sort_order=0,
    )
    session.add_all([category, priority, customer, status])
    await session.flush()

    ticket = Ticket(
        branch_id=branch.id,
        department_id=department.id,
        reference_no=f"TKT-TEST-{uuid.uuid4().hex[:8]}",
        customer_id=customer.id,
        subject="Test subject",
        description="Test description",
        category_id=category.id,
        priority_id=priority.id,
        status_id=status.id,
        channel="web",
        source_locale="ar",
        sla_policy_id=sla_policy.id,
        sla_paused_ms=sla_paused_ms,
        created_at=created_at,
    )
    session.add(ticket)
    await session.flush()
    return ticket, priority, status


async def test_pause_accounting_shifts_deadline_by_paused_duration(db_session):
    branch, department = await _make_branch_department(db_session)
    policy = SlaPolicy(
        branch_id=branch.id, label_ar="سياسة", label_en="Policy",
        first_response_minutes=60, resolution_minutes=120, business_hours_only=False,
    )
    db_session.add(policy)
    await db_session.flush()

    created_at = datetime(2024, 1, 1, tzinfo=UTC)
    ticket, _priority, _status = await _make_ticket(
        db_session, branch, department, created_at=created_at, sla_policy=policy
    )

    service = SlaService(db_session, TenantScope(branch_id=branch.id, department_id=department.id))
    baseline = service.compute_due_dates(ticket, policy, branch)

    ticket.sla_paused_ms = 2 * 60 * 60 * 1000  # 2 hours
    paused = service.compute_due_dates(ticket, policy, branch)

    assert paused.first_response_due_at - baseline.first_response_due_at == timedelta(hours=2)
    assert paused.resolution_due_at - baseline.resolution_due_at == timedelta(hours=2)


async def test_business_hours_policy_does_not_accrue_outside_configured_hours(db_session):
    # Every weekday except Monday is closed, so 120 minutes starting an hour before close rolls
    # over to the *following* Monday's opening time rather than accruing over the weekend.
    branch, department = await _make_branch_department(
        db_session,
        timezone="UTC",
        business_hours={"mon": {"open": "09:00", "close": "17:00"}},
    )
    policy = SlaPolicy(
        branch_id=branch.id, label_ar="سياسة", label_en="Policy",
        first_response_minutes=30, resolution_minutes=120, business_hours_only=True,
    )
    db_session.add(policy)
    await db_session.flush()

    # 2024-01-01 is a Monday; 16:00 leaves only 60 of the needed 120 minutes before 17:00 close.
    created_at = datetime(2024, 1, 1, 16, 0, tzinfo=UTC)
    ticket, _priority, _status = await _make_ticket(
        db_session, branch, department, created_at=created_at, sla_policy=policy
    )

    service = SlaService(db_session, TenantScope(branch_id=branch.id, department_id=department.id))
    due_dates = service.compute_due_dates(ticket, policy, branch)

    # 60 minutes used before Monday's close, remaining 60 minutes resume at the *next* Monday's
    # 09:00 open (the only configured business day) — not at any point over the weekend.
    assert due_dates.resolution_due_at == datetime(2024, 1, 8, 10, 0, tzinfo=UTC)


async def test_sweep_breaches_is_idempotent(db_session):
    branch, department = await _make_branch_department(db_session)
    policy = SlaPolicy(
        branch_id=branch.id, label_ar="سياسة", label_en="Policy",
        first_response_minutes=5, resolution_minutes=10, business_hours_only=False,
    )
    db_session.add(policy)
    await db_session.flush()

    created_at = datetime.now(UTC) - timedelta(days=1)
    ticket, _priority, _status = await _make_ticket(
        db_session, branch, department, created_at=created_at, sla_policy=policy, priority_severity=2
    )

    service = SlaService(db_session, TenantScope(branch_id=None, department_id=None, cross_branch=True))

    # sweep_breaches() scans every open ticket across every tenant (it is a system-wide job),
    # so its aggregate return count also reflects whatever else is in this database (e.g. seed
    # data) — only this test's own ticket's event count is asserted on below.
    await service.sweep_breaches()

    events = await db_session.execute(
        select(TicketEvent).where(
            TicketEvent.ticket_id == ticket.id, TicketEvent.event_type == "sla_breached"
        )
    )
    assert len(events.scalars().all()) == 2  # both first_response and resolution targets are overdue

    await service.sweep_breaches()

    events_after = await db_session.execute(
        select(TicketEvent).where(
            TicketEvent.ticket_id == ticket.id, TicketEvent.event_type == "sla_breached"
        )
    )
    assert len(events_after.scalars().all()) == 2


async def test_override_with_already_past_deadline_is_permitted_and_breaches(db_session):
    branch, department = await _make_branch_department(db_session)
    user = User(
        branch_id=branch.id,
        department_id=department.id,
        email=f"{uuid.uuid4().hex}@example.test",
        password_hash="unused",
        full_name_ar="مستخدم تجريبي",
        full_name_en="Test user",
    )
    db_session.add(user)
    await db_session.flush()

    original_policy = SlaPolicy(
        branch_id=branch.id, label_ar="سياسة أصلية", label_en="Original policy",
        first_response_minutes=600, resolution_minutes=1200, business_hours_only=False,
    )
    override_policy = SlaPolicy(
        branch_id=branch.id, label_ar="سياسة بديلة", label_en="Override policy",
        first_response_minutes=1, resolution_minutes=1, business_hours_only=False,
    )
    db_session.add_all([original_policy, override_policy])
    await db_session.flush()

    created_at = datetime.now(UTC) - timedelta(hours=1)
    ticket, _priority, _status = await _make_ticket(
        db_session, branch, department, created_at=created_at, sla_policy=original_policy
    )

    actor = CurrentActor(
        user_id=user.id,
        scope=TenantScope(branch_id=branch.id, department_id=department.id),
        permissions=frozenset({"ticket.read", "ticket.sla_override"}),
        correlation_id=uuid.uuid4(),
    )
    service = SlaService(db_session, actor.scope)

    updated = await service.override_policy(actor, ticket.id, override_policy.id, "customer escalation")

    assert updated.sla_policy_id == override_policy.id
    assert updated.sla_breach_state == "breached"
