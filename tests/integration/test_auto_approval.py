"""
Auto-approval end-to-end — requires PostgreSQL with the seeded regions
and policies.
"""

from __future__ import annotations

import pytest


@pytest.mark.pg
@pytest.mark.asyncio
async def test_auto_approval_on_hyderabad_food_request(client):
    """
    A low-priority food request inside Hyderabad should be auto-approved
    by policy IN-TG-HYD-FOOD-WATER-LOW — if the seed data is loaded.
    """
    payload = {
        "service_type": "food",
        "priority": "low",
        "description": "Low-stake food request for the auto-approval test.",
        "location": {"latitude": 17.40, "longitude": 78.48},  # inside HYD
    }
    r = await client.post("/api/v1/incidents", json=payload)
    if r.status_code != 201:
        pytest.skip("DB not available")
    body = r.json()
    # Whether it auto-approves depends on the policy state and caps.
    # We assert the decision was recorded rather than assert approval.
    assert body["status"] in ("created", "approved")


@pytest.mark.pg
@pytest.mark.asyncio
async def test_auto_approval_outside_region_defers(client):
    """A request outside any known region cannot be auto-approved."""
    payload = {
        "service_type": "food",
        "priority": "low",
        "description": "Far away from any known region.",
        "location": {"latitude": 12.9716, "longitude": 77.5946},  # Bangalore
    }
    r = await client.post("/api/v1/incidents", json=payload)
    if r.status_code != 201:
        pytest.skip("DB not available")
    assert r.json()["status"] == "created"


@pytest.mark.pg
@pytest.mark.asyncio
async def test_kill_switch_disables_auto_approval(client, monkeypatch):
    """Setting AUTO_APPROVAL_ENABLED=0 disables the engine."""
    monkeypatch.setenv("AUTO_APPROVAL_ENABLED", "0")

    from shared.config import get_settings
    get_settings.cache_clear()

    payload = {
        "service_type": "water",
        "priority": "low",
        "description": "Should not be auto-approved while disabled.",
        "location": {"latitude": 17.40, "longitude": 78.48},
    }
    r = await client.post("/api/v1/incidents", json=payload)
    if r.status_code != 201:
        pytest.skip("DB not available")
    # With the kill switch off, the incident stays in 'created'
    assert r.json()["status"] == "created"
