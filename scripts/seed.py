"""
Idempotent seed script — the rich demo dataset.

Run:  python -m scripts.seed
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from shared.config import get_settings
from shared.db import SessionLocal
from shared.enums import (
    IncidentStatus, OrgType, PersonnelStatus, Priority, ServiceType,
    UnitStatus, UserRole, UserStatus,
)
from shared.models import (
    AutoApprovalDecision, AutoApprovalPolicy, Incident, IncidentUpdate,
    Organization, OrganizationMember, PersonnelStatusRow, Region, Unit,
    UnitStatusRow, User, VolunteerEnrollment,
)
from shared.security import hash_password

# Stable UUIDs so re-seeding is a no-op
ADMIN_ID   = uuid.UUID("10000000-0000-4000-8000-000000000001")
COORD_HYD  = uuid.UUID("10000000-0000-4000-8000-000000000002")
COORD_VJA  = uuid.UUID("10000000-0000-4000-8000-000000000003")
PRIYA      = uuid.UUID("10000000-0000-4000-8000-000000000004")
MOHAN      = uuid.UUID("10000000-0000-4000-8000-000000000005")
SNEHA      = uuid.UUID("10000000-0000-4000-8000-000000000006")
NGO_OWNER  = uuid.UUID("10000000-0000-4000-8000-000000000007")
MED_OWNER  = uuid.UUID("10000000-0000-4000-8000-000000000008")
VOL_RAVI   = uuid.UUID("10000000-0000-4000-8000-000000000009")
VOL_FATIMA = uuid.UUID("10000000-0000-4000-8000-00000000000a")

ORG_NGO    = uuid.UUID("20000000-0000-4000-8000-000000000001")
ORG_MED    = uuid.UUID("20000000-0000-4000-8000-000000000002")
UNIT_1     = uuid.UUID("21000000-0000-4000-8000-000000000001")
UNIT_2     = uuid.UUID("21000000-0000-4000-8000-000000000002")


# Starter regions — the same rectangles as sql/05_regions_and_policies.sql.
# (code, name, WKT boundary in lon/lat order)
REGIONS = [
    ("IN-TG-HYD", "Hyderabad Urban",
     "MULTIPOLYGON(((78.35 17.35, 78.55 17.35, 78.55 17.45, 78.35 17.45, 78.35 17.35)))"),
    ("IN-AP-VJA", "Vijayawada Urban",
     "MULTIPOLYGON(((80.60 16.48, 80.72 16.48, 80.72 16.55, 80.60 16.55, 80.60 16.48)))"),
    ("IN-AP-VTZ", "Visakhapatnam Urban",
     "MULTIPOLYGON(((83.20 17.65, 83.35 17.65, 83.35 17.78, 83.20 17.78, 83.20 17.65)))"),
]


def _upsert_regions(db) -> None:
    """Create the starter regions. `code` is unique, so re-running is a no-op."""
    for code, name, wkt in REGIONS:
        db.execute(
            text(
                "INSERT INTO regions (code, name, boundary) "
                "VALUES (:code, :name, ST_GeomFromText(:wkt, 4326)) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "name": name, "wkt": wkt},
        )
    db.flush()


def _upsert_user(db, uid, email, name, role, *, phone=None, lang="en"):
    # Look up by email, not id: `users.email` is unique, and the admin row is
    # already inserted by migration 0003 under a different id.
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        return existing
    user = User(
        id=uid, email=email, password_hash=hash_password(get_settings().seed_password),
        name=name, phone=phone, role=role, status=UserStatus.active,
        email_verified=True, language=lang,
    )
    db.add(user)
    db.flush()
    return user


def _upsert_org(db, oid, name, owner_id, categories, lat, lng):
    existing = db.get(Organization, oid)
    if existing:
        return existing
    from geoalchemy2.elements import WKTElement
    org = Organization(
        id=oid, name=name, type=OrgType.ngo, owner_user_id=owner_id,
        service_categories=categories,
        service_area_center=WKTElement(f"POINT({lng} {lat})", srid=4326),
        service_radius_km=25.0, capacity=500, available_capacity=420,
        is_verified=True, verified_at=datetime.now(UTC),
        contact_phone=None,
    )
    db.add(org)
    db.flush()
    db.add(OrganizationMember(
        organization_id=oid, user_id=owner_id, role="owner",
        added_by=owner_id, added_at=datetime.now(UTC),
    ))
    db.flush()
    return org


def main() -> None:
    settings = get_settings()
    print(f"Seeding IDRM… password = {settings.seed_password}")

    with SessionLocal() as db:
        # --- users ---------------------------------------------------------
        _upsert_user(db, ADMIN_ID, "admin@idrm.local", "Platform Administrator",
                     UserRole.admin)
        _upsert_user(db, COORD_HYD, "coord.hyd@idrm.local",
                     "Anjali Rao (Coordinator, Hyderabad)", UserRole.coordinator)
        _upsert_user(db, COORD_VJA, "coord.vja@idrm.local",
                     "Kiran Reddy (Coordinator, Vijayawada)", UserRole.coordinator,
                     lang="te")
        _upsert_user(db, PRIYA, "priya.citizen@example.com", "Priya Sharma",
                     UserRole.citizen, lang="hi")
        _upsert_user(db, MOHAN, "mohan.citizen@example.com", "Mohan Kumar",
                     UserRole.citizen, lang="te")
        _upsert_user(db, SNEHA, "sneha.citizen@example.com", "Sneha Iyer",
                     UserRole.citizen)
        _upsert_user(db, NGO_OWNER, "smilinghearts@ngo.example",
                     "Smiling Hearts Foundation", UserRole.provider)
        _upsert_user(db, MED_OWNER, "apmedical@org.example",
                     "AP Medical Response", UserRole.provider, lang="te")
        _upsert_user(db, VOL_RAVI, "volunteer.ravi@example.com",
                     "Ravi Teja (Volunteer)", UserRole.provider, lang="te")
        _upsert_user(db, VOL_FATIMA, "volunteer.fatima@example.com",
                     "Fatima Khan (Volunteer)", UserRole.provider, lang="hi")
        db.commit()

        # --- regions -------------------------------------------------------
        _upsert_regions(db)
        db.commit()
        regions = db.execute(select(Region)).scalars().all()

        # --- organizations -------------------------------------------------
        _upsert_org(db, ORG_NGO, "Smiling Hearts Foundation", NGO_OWNER,
                    [ServiceType.food, ServiceType.water], 17.38, 78.48)
        _upsert_org(db, ORG_MED, "AP Medical Response", MED_OWNER,
                    [ServiceType.medical, ServiceType.rescue], 16.51, 80.65)

        # --- units ---------------------------------------------------------
        if not db.get(Unit, UNIT_1):
            db.add(Unit(id=UNIT_1, organization_id=ORG_NGO, name="Food Truck 01",
                        kind="vehicle", callsign="FT-01", capacity=4))
            db.add(UnitStatusRow(unit_id=UNIT_1, status=UnitStatus.in_quarters,
                                 updated_at=datetime.now(UTC)))
        if not db.get(Unit, UNIT_2):
            db.add(Unit(id=UNIT_2, organization_id=ORG_MED, name="Ambulance 07",
                        kind="ambulance", callsign="AMB-07", capacity=3))
            db.add(UnitStatusRow(unit_id=UNIT_2, status=UnitStatus.in_quarters,
                                 updated_at=datetime.now(UTC)))

        # --- personnel statuses -------------------------------------------
        for uid, status in [
            (VOL_RAVI, PersonnelStatus.available),
            (VOL_FATIMA, PersonnelStatus.off_duty),
            (NGO_OWNER, PersonnelStatus.available),
            (MED_OWNER, PersonnelStatus.responding),
        ]:
            if not db.execute(
                select(PersonnelStatusRow).where(PersonnelStatusRow.user_id == uid)
            ).scalar_one_or_none():
                db.add(PersonnelStatusRow(
                    user_id=uid, status=status, staffing_level=1,
                    updated_at=datetime.now(UTC),
                ))
        db.commit()

        # --- a few incidents ---------------------------------------------
        if not db.execute(select(Incident).limit(1)).scalar_one_or_none():
            from geoalchemy2.elements import WKTElement
            hyd_id = next(r.id for r in regions if r.code == "IN-TG-HYD")
            vja_id = next(r.id for r in regions if r.code == "IN-AP-VJA")

            samples = [
                (ServiceType.water, Priority.medium, "Water supply cut for 3 days in Amberpet colony. ~60 families affected.",
                 PRIYA, hyd_id, 17.40, 78.51, IncidentStatus.approved, True),
                (ServiceType.food, Priority.low, "Need food packets for 25 people at a temporary shelter.",
                 MOHAN, hyd_id, 17.37, 78.49, IncidentStatus.approved, True),
                (ServiceType.medical, Priority.critical, "Elderly woman with chest pain. Ambulance needed urgently.",
                 SNEHA, hyd_id, 17.42, 78.53, IncidentStatus.created, False),
                (ServiceType.rescue, Priority.high, "Family of 5 trapped by flood on the first floor.",
                 MOHAN, vja_id, 16.52, 80.66, IncidentStatus.accepted, False),
            ]
            for svc, pri, desc, req, region, lat, lng, status_, auto in samples:
                inc = Incident(
                    service_type=svc, priority=pri, status=status_,
                    description=desc,
                    location=WKTElement(f"POINT({lng} {lat})", srid=4326),
                    region_id=region, requester_id=req,
                    auto_approved=auto,
                )
                if status_ == IncidentStatus.accepted:
                    inc.assigned_organization_id = ORG_MED
                db.add(inc)
                db.flush()
                db.add(IncidentUpdate(
                    incident_id=inc.id, from_status=None, to_status=IncidentStatus.created,
                    actor_id=req, note="Request created.", created_at=datetime.now(UTC),
                ))
                if auto:
                    db.add(IncidentUpdate(
                        incident_id=inc.id, from_status=IncidentStatus.created,
                        to_status=IncidentStatus.approved, actor_id=None,
                        note="Auto-approved by policy", created_at=datetime.now(UTC),
                    ))
            db.commit()

        # --- volunteer enrollment (pending) -------------------------------
        existing_enroll = db.execute(
            select(VolunteerEnrollment).where(VolunteerEnrollment.user_id == VOL_FATIMA)
        ).scalar_one_or_none()
        if not existing_enroll:
            db.add(VolunteerEnrollment(
                user_id=VOL_FATIMA, scope_type="organization", scope_id=ORG_NGO,
                status="pending", self_enrolled_at=datetime.now(UTC),
            ))
            db.commit()

        # --- region-scoped policies ---------------------------------------
        if not db.execute(select(AutoApprovalPolicy).limit(1)).scalar_one_or_none():
            hyd_id = next(r.id for r in regions if r.code == "IN-TG-HYD")
            db.add(AutoApprovalPolicy(
                code="IN-TG-HYD-FOOD-WATER-LOW", name="Auto-approve food & water — Hyderabad",
                applies_to="incident", priority=10,
                region_scope=[hyd_id],
                service_types=["food", "water"],
                priorities_allowed=["low", "medium"],
                conditions={"max_estimated_cost_inr": 500, "max_per_requester_per_day": 3},
                caps={"per_region_per_day": 500, "per_requester_per_day": 3},
            ))
            db.commit()

        print("✔ Seed complete")
        print("   admin@idrm.local / Admin#2026  (set by migration 0003)")
        print(f"   all seeded users / {settings.seed_password}")


if __name__ == "__main__":
    main()

