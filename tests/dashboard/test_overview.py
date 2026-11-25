"""Overview page: the first card is the triage queue (ADR-0016).

These write rows, so they are `pg` tests and run only on a `*_test` database.
"""

from __future__ import annotations

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dashboard.services.kpi import KPIService
from shared.db import sync_engine
from shared.enums import IncidentStatus, Priority, ServiceType, UserRole, UserStatus
from shared.models.identity import User
from shared.models.incident import Incident
from shared.security import hash_password

pytestmark = pytest.mark.pg

PASSWORD = "overview-test-pass-1"


def _incident(status: IncidentStatus, priority: Priority = Priority.medium) -> Incident:
    return Incident(service_type=ServiceType.food, priority=priority, status=status,
                    description="Test request for the overview card.",
                    location=WKTElement("POINT(78.4867 17.3850)", srid=4326))


def _waiting(db: Session) -> int:
    return db.execute(select(func.count()).select_from(Incident).where(
        Incident.status == IncidentStatus.created, Incident.deleted_at.is_(None),
    )).scalar_one()


def test_card_counts_only_requests_waiting_for_approval():
    with Session(sync_engine) as db:
        before = KPIService(db).summary()
        assert before["incidents_awaiting_approval"] == _waiting(db)

        db.add_all([
            _incident(IncidentStatus.created, Priority.critical),   # counts, and is critical
            _incident(IncidentStatus.approved),                     # does not count
            _incident(IncidentStatus.in_progress),                  # does not count
        ])
        db.flush()
        after = KPIService(db).summary()
        assert after["incidents_awaiting_approval"] == before["incidents_awaiting_approval"] + 1
        assert after["incidents_awaiting_critical"] == before["incidents_awaiting_critical"] + 1
        db.rollback()                                               # leave no rows behind


def test_overview_shows_the_triage_card(dash_client):
    email = f"coord-{uuid.uuid4().hex[:8]}@example.test"
    with Session(sync_engine) as db:
        db.add(User(email=email, password_hash=hash_password(PASSWORD), name="Coord",
                    role=UserRole.coordinator, status=UserStatus.active, email_verified=True))
        db.commit()

    r = dash_client.post("/dashboard/auth/login", data={"email": email, "password": PASSWORD})
    assert r.status_code in (302, 303), r.status_code

    page = dash_client.get("/dashboard/").get_data(as_text=True)
    assert "Waiting for Approval" in page
    assert "Open Incidents" not in page
    assert "status=created" in page              # the card links to exactly what it counts
