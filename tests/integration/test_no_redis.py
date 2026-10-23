"""Prove the platform works without Redis."""

from __future__ import annotations

import os

import pytest


@pytest.mark.asyncio
async def test_health_without_redis(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "")

    from shared.cache import get_redis, reset_availability
    reset_availability()

    assert get_redis() is None

    # The app still responds
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v1/health")
        assert r.status_code == 200

