"""One test per ScopingMode (S1-S6), verifying _scoped_select() includes/excludes rows
correctly by inspecting the compiled SQL — no live database required (constitution Principle
XIV; DEBT.md: no testcontainers this sprint)."""

import uuid

from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.department import Department
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.user import User
from app.repositories.scoped_repository import ScopedRepository, ScopingMode, TenantScope

BRANCH_ID = uuid.uuid4()
DEPT_ID = uuid.uuid4()
SCOPE = TenantScope(branch_id=BRANCH_ID, department_id=DEPT_ID)


def _sql(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def _hex(value: uuid.UUID) -> str:
    # asyncpg's literal UUID binding renders as an unhyphenated hex string.
    return value.hex


class _S6Repo(ScopedRepository[Branch]):
    model = Branch
    scoping_mode = ScopingMode.S6_GLOBAL


class _S3Repo(ScopedRepository[Department]):
    model = Department
    scoping_mode = ScopingMode.S3_BRANCH_ONLY


class _S2Repo(ScopedRepository[User]):
    model = User
    scoping_mode = ScopingMode.S2_BRANCH_DEPT_OPTIONAL


class _S1Repo(ScopedRepository[Ticket]):
    model = Ticket
    scoping_mode = ScopingMode.S1_FULL


class _S4Repo(ScopedRepository[TicketEvent]):
    model = TicketEvent
    scoping_mode = ScopingMode.S4_TRANSITIVE
    parent_model = Ticket
    parent_fk_column = "ticket_id"


class _S5Repo(ScopedRepository[AuditLog]):
    model = AuditLog
    scoping_mode = ScopingMode.S5_SYSTEM_NULLABLE


def test_s6_global_has_no_predicate():
    repo = _S6Repo(session=None, scope=SCOPE)
    sql = _sql(repo._scoped_select())
    assert "WHERE" not in sql


def test_s3_branch_only_filters_branch_id():
    repo = _S3Repo(session=None, scope=SCOPE)
    sql = _sql(repo._scoped_select())
    assert "departments.branch_id" in sql
    assert _hex(BRANCH_ID) in sql
    assert "department_id =" not in sql


def test_s2_branch_required_department_optional():
    repo = _S2Repo(session=None, scope=SCOPE)
    sql = _sql(repo._scoped_select())
    assert "users.branch_id" in sql
    assert _hex(BRANCH_ID) in sql
    assert "users.department_id" in sql
    assert "IS NULL" in sql


def test_s1_full_filters_both_branch_and_department():
    repo = _S1Repo(session=None, scope=SCOPE)
    sql = _sql(repo._scoped_select())
    assert "tickets.branch_id" in sql
    assert "tickets.department_id" in sql
    assert _hex(BRANCH_ID) in sql
    assert _hex(DEPT_ID) in sql


def test_s5_system_nullable_includes_null_branch():
    repo = _S5Repo(session=None, scope=SCOPE)
    sql = _sql(repo._scoped_select())
    assert "audit_logs.branch_id" in sql
    assert "IS NULL" in sql


def test_s1_cross_branch_skips_predicate():
    repo = _S1Repo(session=None, scope=TenantScope(branch_id=BRANCH_ID, department_id=DEPT_ID, cross_branch=True))
    sql = _sql(repo._scoped_select())
    assert "WHERE" not in sql


def test_s4_joins_parent_and_applies_parent_predicate_never_own_branch_department():
    repo = _S4Repo(session=None, scope=SCOPE)
    stmt = repo._scoped_select()
    sql = _sql(stmt)
    assert "JOIN tickets" in sql
    # The parent's (tickets, S1) predicate is applied via the join — never a direct
    # ticket_events.branch_id/department_id predicate, because ticket_events has no such columns.
    assert "ticket_events.branch_id" not in sql
    assert "ticket_events.department_id" not in sql
    assert "tickets.branch_id" in sql
    assert "tickets.department_id" in sql
