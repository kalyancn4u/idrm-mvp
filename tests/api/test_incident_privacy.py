"""Who sees how much of a help request, through the API (ADR-0015, G-1, G-2, WF3).

These write rows, so they are `pg` tests and run only on a `*_test` database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from geoalchemy2.elements import WKTElement

from shared.db import async_session
from shared.enums import IncidentStatus, OrgMemberRole, OrgType, Priority, ServiceType, UserRole, UserStatus
from shared.models.identity import User
from shared.models.incident import Incident
from shared.models.organization import Organization, OrganizationMember
from shared.security import hash_password

pytestmark = pytest.mark.pg

PASSWORD = "privacy-test-pass-1"
LAT, LNG = 17.3850, 78.4867


async def _world():
    """Create users, two organizations (one verified) and three requests."""
    tag = uuid.uuid4().hex[:8]
    now = datetime.now(UTC)
    async with async_session() as db:
        def user(name, role):
            u = User(email=f"{name}-{tag}@example.test", password_hash=hash_password(PASSWORD),
                     name=name.title(), role=role, status=UserStatus.active, email_verified=True)
            db.add(u)
            return u

        citizen = user("citizen", UserRole.citizen)
        trusted = user("trusted", UserRole.provider)
        stranger = user("stranger", UserRole.provider)
        coordinator = user("coord", UserRole.coordinator)
        await db.flush()

        def org(name, owner, verified):
            o = Organization(name=f"{name}-{tag}", type=OrgType.ngo, owner_user_id=owner.id,
                             is_verified=verified)
            db.add(o)
            return o

        good = org("verified", trusted, True)
        bad = org("unverified", stranger, False)
        await db.flush()
        for o, u in ((good, trusted), (bad, stranger)):
            db.add(OrganizationMember(organization_id=o.id, user_id=u.id,
                                      role=OrgMemberRole.owner, added_at=now))

        def request(status, assigned=None):
            i = Incident(service_type=ServiceType.rescue, priority=Priority.critical, status=status,
                         description="Water at knee height, call 9800000001, elderly woman alone.",
                         location=WKTElement(f"POINT({LNG} {LAT})", srid=4326),
                         requester_id=citizen.id, assigned_organization_id=assigned)
            db.add(i)
            return i

        waiting = request(IncidentStatus.created)
        open_ = request(IncidentStatus.approved)
        ours = request(IncidentStatus.accepted, assigned=good.id)
        await db.commit()
        return {
            "emails": {k: v.email for k, v in
                       (("citizen", citizen), ("trusted", trusted),
                        ("stranger", stranger), ("coordinator", coordinator))},
            "waiting": str(waiting.id), "open": str(open_.id), "ours": str(ours.id),
        }


async def _login(client, email):
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


async def test_guest_tracking_token_is_shown_once(client):
    r = await client.post("/api/v1/incidents", json={
        "service_type": "water", "priority": "medium",
        "description": "Drinking water needed at the relief camp.",
        "location": {"latitude": LAT, "longitude": LNG},
    })
    assert r.status_code == 201
    token = r.json()["tracking_token"]
    assert token
    tracked = await client.get(f"/api/v1/incidents/track/{token}")
    assert tracked.status_code == 200
    assert "tracking_token" not in tracked.json()


async def test_provider_outside_a_verified_org_sees_nothing(client):
    w = await _world()
    h = await _login(client, w["emails"]["stranger"])
    assert (await client.get("/api/v1/incidents", headers=h)).status_code == 403
    assert (await client.get(f"/api/v1/incidents/nearby?latitude={LAT}&longitude={LNG}",
                             headers=h)).status_code == 403
    assert (await client.get(f"/api/v1/incidents/{w['open']}", headers=h)).status_code == 403
    r = await client.post(f"/api/v1/incidents/{w['open']}/accept", headers=h, json={})
    assert r.status_code == 403


async def test_verified_provider_gets_coarse_open_work_and_full_own_work(client):
    w = await _world()
    h = await _login(client, w["emails"]["trusted"])

    r = await client.get("/api/v1/incidents?limit=100", headers=h)
    assert r.status_code == 200
    by_id = {row["id"]: row for row in r.json()["data"]}
    assert w["waiting"] not in by_id                  # not approved: invisible

    card = by_id[w["open"]]                           # approved: coarse
    assert card["view"] == "coarse"
    assert card["description"] is None
    # The summary tells the need without the phone number in the text.
    assert "elderly woman alone" in card["summary"]
    assert "9800000001" not in card["summary"] and "[number]" in card["summary"]
    assert card["requester_id"] is None
    assert card["latitude"] == pytest.approx(17.39)
    assert card["longitude"] == pytest.approx(78.49)
    assert "tracking_token" not in card

    mine = by_id[w["ours"]]                           # our org's job: full
    assert mine["view"] == "full"
    assert mine["description"].startswith("Water")
    assert mine["latitude"] == pytest.approx(LAT)
    assert mine["requester_id"] is None               # never for providers

    near = await client.get(f"/api/v1/incidents/nearby?latitude={LAT}&longitude={LNG}&radius_km=5",
                            headers=h)
    assert near.status_code == 200
    ids = {row["id"] for row in near.json()["data"]}
    assert w["waiting"] not in ids and w["open"] in ids

    # The timeline holds free text: full view only.
    assert (await client.get(f"/api/v1/incidents/{w['open']}/updates", headers=h)).status_code == 403
    assert (await client.get(f"/api/v1/incidents/{w['waiting']}", headers=h)).status_code == 403


async def test_coordinator_still_sees_everything(client):
    w = await _world()
    h = await _login(client, w["emails"]["coordinator"])
    r = await client.get(f"/api/v1/incidents/{w['waiting']}", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["view"] == "full"
    assert body["requester_id"] is not None
    assert "tracking_token" not in body
