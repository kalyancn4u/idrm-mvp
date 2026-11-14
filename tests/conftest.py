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


def pytest_collection_modifyitems(config, items):
    if not any("pg" in item.keywords for item in items):
        return
    if _database_reachable():
        return
    skip = pytest.mark.skip(reason="needs PostgreSQL + PostGIS (see `make infra-up migrate seed`)")
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
