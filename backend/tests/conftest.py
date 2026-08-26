import asyncio
import sys

import pytest


@pytest.fixture(scope="session")
def event_loop_policy():
    """asyncpg's Windows default (ProactorEventLoop) intermittently breaks connection teardown —
    a well-known asyncpg/Windows incompatibility, unrelated to this codebase. Selector policy is
    the standard workaround for local dev on Windows; docker compose (Linux) never hits this.
    (pytest-asyncio flags overriding this fixture as deprecated in favor of the
    `pytest_asyncio_loop_factories` hook, but that hook's exact return shape isn't stable across
    the pytest-asyncio 1.x line yet — this fixture form still works correctly.)"""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.get_event_loop_policy()
