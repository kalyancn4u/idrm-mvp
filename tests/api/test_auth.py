"""Auth endpoint contract tests."""

from __future__ import annotations

import pytest


@pytest.mark.pg
async def test_health_ok_with_database(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_health_never_leaks_error_text(client):
    """Up or down, the body carries no database error message."""
    r = await client.get("/api/v1/health")
    assert r.status_code in {200, 503}          # 503 = database down, by design
    assert set(r.json()["components"]["database"]) == {"ok"}


async def test_me_requires_auth(client):
    r = await client.get("/api/v1/users/me")
    assert r.status_code == 401


@pytest.mark.pg
async def test_invalid_login_returns_generic_message(client):
    r = await client.post("/api/v1/auth/login",
                          json={"email": "nobody@x.example", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


async def test_register_rejects_short_password(client):
    r = await client.post("/api/v1/auth/register",
                          json={"email": "a@b.example", "password": "short",
                                "name": "Tester"})
    assert r.status_code == 422


@pytest.mark.parametrize("role", ["admin", "coordinator"])
async def test_register_refuses_privileged_roles(client, role):
    """Nobody can make themselves staff by asking for it at sign-up."""
    r = await client.post("/api/v1/auth/register",
                          json={"email": "a@b.example", "password": "longenough1",
                                "name": "Tester", "role": role})
    assert r.status_code == 403


async def test_spoofed_headers_do_not_reset_the_rate_limit(client):
    """The limiter counts per real client address, not per header value."""
    codes = []
    for i in range(12):
        r = await client.post(
            "/api/v1/auth/register",
            headers={"Authorization": f"Bearer fake-{i}", "X-Forwarded-For": f"10.0.0.{i}"},
            json={"email": "a@b.example", "password": "longenough1",
                  "name": "Tester", "role": "admin"},
        )
        codes.append(r.status_code)
    assert codes[0] == 403          # the first calls reach the handler...
    assert codes[-1] == 429         # ...and the limit still bites despite new headers each time
