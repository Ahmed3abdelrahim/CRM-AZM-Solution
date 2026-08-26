"""Legal transition succeeds; illegal transition raises IllegalTransitionError naming current +
permitted statuses; requires_reason=true without a reason is rejected; a transition whose
required_permission the actor lacks is rejected (Testing Proportionality — status transition
legality; also this batch's own gate, PLAN.md §6).

Requires a live Postgres reachable via DATABASE_URL, migrated to head — same as test_audit.py
(DEBT.md D03: no testcontainers this sprint)."""

import uuid

import pytest

from app.core.errors import IllegalTransitionError, ValidationError
from app.core.permissions import CurrentActor, PermissionDeniedError
from app.db import async_session_factory
from app.models.branch import Branch
from app.models.category import Category
from app.models.customer import Customer
from app.models.department import Department
from app.models.priority import Priority
from app.models.status_transition import StatusTransition
from app.models.ticket import Ticket
from app.models.ticket_status import TicketStatus
from app.models.user import User
from app.repositories.scoped_repository import TenantScope
from app.services.ticket_transition_service import TicketTransitionService


@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session
        await session.rollback()


async def _make_actor(session, permissions=("ticket.read",)):
    branch = Branch(
        code=f"seed-{uuid.uuid4().hex[:8]}",
        label_ar="فرع تجريبي",
        label_en="Seed branch",
        timezone="Asia/Riyadh",
        business_hours={"sun": ["09:00", "17:00"]},
    )
    session.add(branch)
    await session.flush()

    department = Department(
        branch_id=branch.id, code=f"dept-{uuid.uuid4().hex[:6]}", label_ar="قسم", label_en="Department"
    )
    session.add(department)
    await session.flush()

    user = User(
        branch_id=branch.id,
        department_id=department.id,
        email=f"{uuid.uuid4().hex}@example.test",
        password_hash="unused",
        full_name_ar="مستخدم تجريبي",
        full_name_en="Test user",
    )
    session.add(user)
    await session.flush()

    actor = CurrentActor(
        user_id=user.id,
        scope=TenantScope(branch_id=branch.id, department_id=department.id),
        permissions=frozenset(permissions),
        correlation_id=uuid.uuid4(),
    )
    return actor, branch, department


async def _make_ticket(session, branch, department):
    category = Category(branch_id=branch.id, label_ar="تصنيف", label_en="Category")
    priority = Priority(
        branch_id=branch.id, code="p1", label_ar="عالية", label_en="High", severity=1, color="#ff0000"
    )
    customer = Customer(
        branch_id=branch.id,
        department_id=department.id,
        customer_type="individual",
        full_name_ar="عميل تجريبي",
        preferred_locale="ar",
    )
    session.add_all([category, priority, customer])
    await session.flush()

    status_from = TicketStatus(
        branch_id=branch.id, code="s_from", label_ar="من", label_en="From",
        is_terminal=False, pauses_sla=False, sort_order=0,
    )
    status_to = TicketStatus(
        branch_id=branch.id, code="s_to", label_ar="إلى", label_en="To",
        is_terminal=False, pauses_sla=False, sort_order=1,
    )
    status_other = TicketStatus(
        branch_id=branch.id, code="s_other", label_ar="أخرى", label_en="Other",
        is_terminal=False, pauses_sla=False, sort_order=2,
    )
    session.add_all([status_from, status_to, status_other])
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
        status_id=status_from.id,
        channel="web",
        source_locale="ar",
    )
    session.add(ticket)
    await session.flush()

    return ticket, status_from, status_to, status_other


async def test_legal_transition_succeeds(db_session):
    actor, branch, department = await _make_actor(db_session)
    ticket, status_from, status_to, _status_other = await _make_ticket(db_session, branch, department)
    db_session.add(
        StatusTransition(
            branch_id=branch.id, from_status_id=status_from.id, to_status_id=status_to.id, requires_reason=False
        )
    )
    await db_session.flush()

    service = TicketTransitionService(db_session, actor.scope)
    updated = await service.change_status(actor, ticket.id, status_to.id, None)

    assert updated.status_id == status_to.id


async def test_illegal_transition_names_current_and_permitted_statuses(db_session):
    actor, branch, department = await _make_actor(db_session)
    ticket, status_from, status_to, status_other = await _make_ticket(db_session, branch, department)
    db_session.add(
        StatusTransition(
            branch_id=branch.id, from_status_id=status_from.id, to_status_id=status_to.id, requires_reason=False
        )
    )
    await db_session.flush()

    service = TicketTransitionService(db_session, actor.scope)
    with pytest.raises(IllegalTransitionError) as exc_info:
        await service.change_status(actor, ticket.id, status_other.id, None)

    assert exc_info.value.current_status_id == status_from.id
    assert status_to.id in exc_info.value.permitted_status_ids
    assert status_other.id not in exc_info.value.permitted_status_ids


async def test_requires_reason_without_reason_is_rejected(db_session):
    actor, branch, department = await _make_actor(db_session)
    ticket, status_from, status_to, _status_other = await _make_ticket(db_session, branch, department)
    db_session.add(
        StatusTransition(
            branch_id=branch.id, from_status_id=status_from.id, to_status_id=status_to.id, requires_reason=True
        )
    )
    await db_session.flush()

    service = TicketTransitionService(db_session, actor.scope)
    with pytest.raises(ValidationError):
        await service.change_status(actor, ticket.id, status_to.id, None)

    # Supplying a reason succeeds.
    updated = await service.change_status(actor, ticket.id, status_to.id, "closing per customer request")
    assert updated.status_id == status_to.id


async def test_transition_denied_when_actor_lacks_required_permission(db_session):
    actor, branch, department = await _make_actor(db_session, permissions=("ticket.read",))
    ticket, status_from, status_to, _status_other = await _make_ticket(db_session, branch, department)
    db_session.add(
        StatusTransition(
            branch_id=branch.id,
            from_status_id=status_from.id,
            to_status_id=status_to.id,
            requires_reason=False,
            required_permission="ticket.reopen",
        )
    )
    await db_session.flush()

    service = TicketTransitionService(db_session, actor.scope)
    with pytest.raises(PermissionDeniedError) as exc_info:
        await service.change_status(actor, ticket.id, status_to.id, None)

    assert exc_info.value.code == "ticket.reopen"
