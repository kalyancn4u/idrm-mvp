"""
Auto-approval end-to-end — requires PostgreSQL with the seeded regions
and policies (`make migrate seed`).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.pg


def _food_request(lat: float, lng: float, text: str) -> dict:
    return {
        "service_type": "food",
        "priority": "low",
        "description": text,
        "location": {"latitude": lat, "longitude": lng},
    }


async def test_auto_approval_on_hyderabad_food_request(client):
    """
    A low-priority food request inside Hyderabad is auto-approved by the
    seeded policy IN-TG-HYD-FOOD-WATER-LOW.
    """
    r = await client.post("/api/v1/incidents",
                          json=_food_request(17.40, 78.48, "Low-stake food request for the auto-approval test."))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "approved"
    assert body["auto_approved"] is True


async def test_auto_approval_outside_region_defers(client):
    """A request outside any known region is left for a human."""
    r = await client.post("/api/v1/incidents",
                          json=_food_request(12.9716, 77.5946, "Far away from any known region."))  # Bangalore
    assert r.status_code == 201
    assert r.json()["status"] == "created"
    assert r.json()["auto_approved"] is False


async def test_kill_switch_disables_auto_approval(client, monkeypatch):
    """AUTO_APPROVAL_ENABLED=0 turns the engine off."""
    from shared.config import get_settings

    monkeypatch.setenv("AUTO_APPROVAL_ENABLED", "0")
    get_settings.cache_clear()       # restored by the autouse fixture afterwards

    r = await client.post("/api/v1/incidents",
                          json=_food_request(17.40, 78.48, "Should not be auto-approved while disabled."))
    assert r.status_code == 201
    assert r.json()["status"] == "created"
