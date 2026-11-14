"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Tests marked `pg` need a real database. When none is reachable they are
# SKIPPED, visibly, instead of being written to "pass" on a server error.
# ---------------------------------------------------------------------------
def _database_reachable() -> bool:
    try:
        from sqlalchemy import text

        from shared.db import sync_engine

        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _is_test_database() -> bool:
    """
    The database tests INSERT rows. They may only do that in a database whose
    name ends in `_test` — never in the development or production one.
    Set IDRM_TESTS_ON_ANY_DB=1 to override, knowing what that means.
    """
    from sqlalchemy.engine import make_url

    from shared.config import get_settings

    if os.environ.get("IDRM_TESTS_ON_ANY_DB") == "1":
        return True
    name = make_url(get_settings().database_url).database or ""
    return name.endswith("_test")


def pytest_collection_modifyitems(config, items):
    if not any("pg" in item.keywords for item in items):
        return
    if not _is_test_database():
        reason = "database tests only run on a database named *_test (run `make test-db`, then `make test`)"
    elif not _database_reachable():
        reason = "needs PostgreSQL + PostGIS (run `make infra-up test-db`)"
    else:
        return
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if "pg" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _clean_process_state():
    """
    Settings, the Redis connection and the in-process rate limiter are cached
    for the life of the process. A test that changes an environment variable
    would otherwise be ignored (old settings still cached) or would leak into
    the tests that run after it. Reset them before and after every test.
    """
    from shared.cache import reset_availability
    from shared.config import get_settings
    from shared.rate_limit import reset_rate_limits

    def reset():
        get_settings.cache_clear()
        reset_availability()
        reset_rate_limits()

    reset()
    yield
    reset()


@pytest.fixture()
async def client():
    os.environ.setdefault("APP_ENV", "testing")
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture()
def dash_app():
    from dashboard import create_dashboard

    app = create_dashboard()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture()
def dash_client(dash_app):
    return dash_app.test_client()
