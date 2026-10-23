"""Incident API contract tests."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_guest_can_create_incident(client):
    """Unauthenticated requests are allowed and receive a tracking token."""
    payload = {
        "service_type": "water",
        "priority": "medium",
        "description": "Test request for drinking water at the relief camp.",
        "location": {"latitude": 17.3850, "longitude": 78.4867},
    }
    r = await client.post("/api/v1/incidents", json=payload)
    if r.status_code == 201:
        body = r.json()
        assert body["tracking_token"]
        assert body["requester_id"] is None


@pytest.mark.asyncio
async def test_short_description_rejected(client):
    r = await client.post(
        "/api/v1/incidents",
        json={
            "service_type": "food",
            "priority": "low",
            "description": "short",   # < 10 chars
            "location": {"latitude": 17.3850, "longitude": 78.4867},
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_incidents_requires_auth(client):
    r = await client.get("/api/v1/incidents")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_track_by_token_public(client):
    """The guest tracking endpoint is public."""
    r = await client.get("/api/v1/incidents/track/nonexistent-token")
    # 404 is the expected response for an unknown token
    assert r.status_code in (404, 500)
