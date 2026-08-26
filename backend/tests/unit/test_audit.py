"""A mutating call through AdminCrudService produces exactly one AuditLog row with correct
before/after; a forced failure inside the wrapped call leaves zero new rows, because
`audited_via`'s AuditLog is only ever added to the session AFTER the wrapped method returns
successfully (app/core/audit.py) — an exception propagates through get_session()'s rollback
(app/db.py) before that add() is ever reached (Testing Proportionality; this batch's own gate,
PLAN.md §6).

Requires a live Postgres reachable via DATABASE_URL, migrated to head — DEBT.md D03: no
testcontainers this sprint, tests run against whatever PG the developer has up."""

import uuid

import pytest
from sqlalchemy import func, select

from app.core.permissions import CurrentActor
from app.db import async_session_factory
from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.user import User
from app.repositories.scoped_repository import TenantScope
from app.schemas.role import BranchCreate
from app.services.admin_crud_service import BranchCrudService


@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session
        await session.rollback()


async def _make_actor(session, permissions=("admin.config",)) -> CurrentActor:
    branch = Branch(
        code=f"seed-{uuid.uuid4().hex[:8]}",
        label_ar="فرع تجريبي",
        label_en="Seed branch",
        timezone="Asia/Riyadh",
        business_hours={"sun": ["09:00", "17:00"]},
    )
    session.add(branch)
    await session.flush()

    user = User(
        branch_id=branch.id,
        email=f"{uuid.uuid4().hex}@example.test",
        password_hash="unused",
        full_name_ar="مستخدم تجريبي",
        full_name_en="Test user",
    )
    session.add(user)
    await session.flush()

    return CurrentActor(
        user_id=user.id,
        scope=TenantScope(branch_id=branch.id, department_id=None),
        permissions=frozenset(permissions),
        correlation_id=uuid.uuid4(),
    )


def _branch_payload() -> BranchCreate:
    return BranchCreate(
        code=f"br-{uuid.uuid4().hex[:8]}",
        label_ar="فرع جديد",
        label_en="New branch",
        timezone="Asia/Riyadh",
        business_hours={"sun": ["09:00", "17:00"]},
    )


async def test_admin_crud_create_writes_exactly_one_audit_row(db_session):
    actor = await _make_actor(db_session)
    service = BranchCrudService(db_session, actor.scope)

    payload = _branch_payload()
    branch = await service.create(actor, payload)
    # audited_via() adds the AuditLog to the session but relies on the request-scoped
    # get_session() to flush/commit (app/db.py) — this test drives the session directly, so it
    # must flush itself before querying back what's pending.
    await db_session.flush()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "branch", AuditLog.entity_id == branch.id)
    )
    rows = result.scalars().all()

    assert len(rows) == 1
    row = rows[0]
    assert row.action == "create"
    assert row.before is None
    assert row.after["code"] == payload.code
    assert row.after["label_ar"] == payload.label_ar
    assert row.actor_id == actor.user_id
    assert row.correlation_id == actor.correlation_id


async def test_failed_mutation_leaves_zero_new_audit_rows(db_session, monkeypatch):
    actor = await _make_actor(db_session)
    service = BranchCrudService(db_session, actor.scope)

    count_before = (await db_session.execute(select(func.count()).select_from(AuditLog))).scalar_one()

    async def _boom(values):
        raise RuntimeError("simulated failure inside the wrapped call")

    monkeypatch.setattr(service.repository, "create", _boom)

    with pytest.raises(RuntimeError):
        await service.create(actor, _branch_payload())

    count_after = (await db_session.execute(select(func.count()).select_from(AuditLog))).scalar_one()
    assert count_after == count_before
