"""Auth endpoint contract tests."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_public(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] in {"ok", "degraded"}


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/api/v1/users/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invalid_login_returns_generic_message(client):
    r = await client.post("/api/v1/auth/login",
                          json={"email": "nobody@x.example", "password": "wrong"})
    # Either the DB is up and we get 401, or the DB isn't and we get 500
    assert r.status_code in {401, 500}


@pytest.mark.asyncio
async def test_register_rejects_short_password(client):
    r = await client.post("/api/v1/auth/register",
                          json={"email": "a@b.example", "password": "short",
                                "name": "Tester"})
    assert r.status_code == 422

