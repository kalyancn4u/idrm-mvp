"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


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

