"""Incident API contract tests."""

from __future__ import annotations

import pytest


@pytest.mark.pg
async def test_guest_can_create_incident(client):
    """Unauthenticated requests are allowed and receive a tracking token."""
    payload = {
        "service_type": "water",
        "priority": "medium",
        "description": "Test request for drinking water at the relief camp.",
        "location": {"latitude": 17.3850, "longitude": 78.4867},
    }
    r = await client.post("/api/v1/incidents", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["tracking_token"]
    assert body["requester_id"] is None
    # Coordinates come back as sent (they used to be null).
    assert body["latitude"] == pytest.approx(17.3850)
    assert body["longitude"] == pytest.approx(78.4867)


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


async def test_list_incidents_requires_auth(client):
    r = await client.get("/api/v1/incidents")
    assert r.status_code == 401


async def test_nearby_is_reachable(client):
    """`/incidents/nearby` must reach its own handler (401), not be read as an id (422)."""
    r = await client.get("/api/v1/incidents/nearby?latitude=17.4&longitude=78.5")
    assert r.status_code == 401


async def test_incident_detail_requires_auth(client):
    r = await client.get("/api/v1/incidents/00000000-0000-4000-8000-000000000001")
    assert r.status_code == 401


@pytest.mark.pg
async def test_track_by_token_public(client):
    """The guest tracking endpoint is public; an unknown token is a 404."""
    r = await client.get("/api/v1/incidents/track/nonexistent-token")
    assert r.status_code == 404
