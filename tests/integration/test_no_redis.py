"""Prove the platform works without Redis."""

from __future__ import annotations

import pytest


def test_empty_redis_url_disables_the_cache(monkeypatch):
    from shared.cache import get_redis, reset_availability
    from shared.config import get_settings

    monkeypatch.setenv("REDIS_URL", "")
    get_settings.cache_clear()
    reset_availability()

    assert get_redis() is None


@pytest.mark.pg
async def test_health_without_redis(client, monkeypatch):
    from shared.cache import reset_availability
    from shared.config import get_settings

    monkeypatch.setenv("REDIS_URL", "")
    get_settings.cache_clear()
    reset_availability()

    r = await client.get("/api/v1/health")
    assert r.status_code == 200
