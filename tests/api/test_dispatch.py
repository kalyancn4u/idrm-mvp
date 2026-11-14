"""Dispatch API contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.dispatch.router import AssignBody, OfferBody

INCIDENT = "00000000-0000-4000-8000-000000000001"
UNIT = "00000000-0000-4000-8000-000000000002"


async def test_dispatch_board_requires_auth(client):
    r = await client.get("/api/v1/dispatch/board")
    assert r.status_code == 401


async def test_dispatch_assign_requires_coordinator(client):
    r = await client.post("/api/v1/dispatch/assign",
                          json={"incident_id": INCIDENT, "unit_id": UNIT})
    assert r.status_code == 401


@pytest.mark.parametrize("model", [AssignBody, OfferBody])
def test_target_is_required(model):
    """Assigning or offering to nobody is a validation error."""
    with pytest.raises(ValidationError):
        model(incident_id=INCIDENT, unit_id=None, user_id=None)
    assert model(incident_id=INCIDENT, unit_id=UNIT).unit_id is not None
