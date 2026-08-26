"""require_permission/require_permission_via grant/deny correctly for a CurrentActor with/
without the code (Testing Proportionality — permission checks). No live database required —
CurrentActor is a plain dataclass and the decorators never touch a session."""

import uuid

import pytest

from app.core.permissions import CurrentActor, PermissionDeniedError, require_permission, require_permission_via
from app.repositories.scoped_repository import TenantScope


def _actor(permissions: set[str]) -> CurrentActor:
    return CurrentActor(
        user_id=uuid.uuid4(),
        scope=TenantScope(branch_id=uuid.uuid4(), department_id=uuid.uuid4()),
        permissions=frozenset(permissions),
        correlation_id=uuid.uuid4(),
    )


class _Service:
    @require_permission("widget.read")
    async def read(self, actor: CurrentActor) -> str:
        return "ok"


async def test_require_permission_grants_when_code_present():
    assert await _Service().read(_actor({"widget.read"})) == "ok"


async def test_require_permission_denies_when_code_absent():
    with pytest.raises(PermissionDeniedError) as exc_info:
        await _Service().read(_actor(set()))
    assert exc_info.value.code == "widget.read"


class _ViaService:
    read_permission = "widget.read"

    @require_permission_via(lambda self: self.read_permission)
    async def read(self, actor: CurrentActor) -> str:
        return "ok"


async def test_require_permission_via_grants_when_code_present():
    assert await _ViaService().read(_actor({"widget.read"})) == "ok"


async def test_require_permission_via_denies_when_code_absent():
    with pytest.raises(PermissionDeniedError) as exc_info:
        await _ViaService().read(_actor({"some.other.code"}))
    assert exc_info.value.code == "widget.read"


async def test_require_permission_via_reads_code_from_subclass_instance():
    """The whole reason require_permission_via exists: a subclass overriding the class attribute
    changes which code is checked, even though the decorator was applied once on the base."""

    class _Subclass(_ViaService):
        read_permission = "other.read"

    assert await _Subclass().read(_actor({"other.read"})) == "ok"
    with pytest.raises(PermissionDeniedError) as exc_info:
        await _Subclass().read(_actor({"widget.read"}))
    assert exc_info.value.code == "other.read"
