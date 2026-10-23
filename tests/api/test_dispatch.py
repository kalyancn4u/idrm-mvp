"""Dispatch API contract tests."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_dispatch_board_requires_auth(client):
    r = await client.get("/api/v1/dispatch/board")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_dispatch_assign_requires_coordinator(client):
    r = await client.post(
        "/api/v1/dispatch/assign",
        json={"incident_id": "00000000-0000-4000-8000-000000000001"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_offer_requires_resource(client):
    """Offering without a unit or user is a validation error."""
    # (We test the schema, not the auth path — both are validated in order.)
    from pydantic import ValidationError

    from app.modules.dispatch.router import OfferBody

    with pytest.raises(ValidationError):
        OfferBody(incident_id="00000000-0000-4000-8000-000000000001", unit_id=None, user_id=None)
