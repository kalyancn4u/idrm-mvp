"""Organizations read + verify."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from shared.audit import log_sync
from shared.models.organization import Organization, VolunteerEnrollment


class OrganizationService:
    def __init__(self, session):
        self.db = session

    def list(self, *, page: int, limit: int, verified: bool | None = None, q: str | None = None):
        conditions = [Organization.deleted_at.is_(None)]
        if verified is not None:
            conditions.append(Organization.is_verified.is_(verified))
        if q:
            conditions.append(Organization.name.ilike(f"%{q}%"))
        total = self.db.execute(
            select(func.count()).select_from(Organization).where(*conditions)
        ).scalar_one()
        rows = list(self.db.execute(
            select(Organization).where(*conditions)
            .order_by(Organization.created_at.desc())
            .offset((page - 1) * limit).limit(limit)
        ).scalars().all())
        return rows, total

    def get(self, org_id: uuid.UUID) -> Organization | None:
        return self.db.get(Organization, org_id)

    def verify(self, org_id: uuid.UUID, actor_id: uuid.UUID):
        org = self.get(org_id)
        if org is None:
            return None
        org.is_verified = True
        org.verified_by = actor_id
        org.verified_at = datetime.now(UTC)
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dashboard.organization.verified",
                 resource_type="organization", resource_id=org_id)
        return org

    def unverify(self, org_id: uuid.UUID, actor_id: uuid.UUID):
        org = self.get(org_id)
        if org is None:
            return None
        org.is_verified = False
        org.verified_by = None
        org.verified_at = None
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dashboard.organization.unverified",
                 resource_type="organization", resource_id=org_id)
        return org

    def pending_volunteers(self):
        return list(self.db.execute(
            select(VolunteerEnrollment).where(VolunteerEnrollment.status == "pending")
            .order_by(VolunteerEnrollment.self_enrolled_at.asc())
        ).scalars().all())

    def approve_volunteer(self, enrollment_id: uuid.UUID, actor_id: uuid.UUID):
        e = self.db.get(VolunteerEnrollment, enrollment_id)
        if e is None:
            return None
        e.status = "active"
        e.approved_by = actor_id
        e.approved_at = datetime.now(UTC)
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dashboard.volunteer.approved",
                 resource_type="volunteer_enrollment", resource_id=enrollment_id)
        return e

    def reject_volunteer(self, enrollment_id: uuid.UUID, actor_id: uuid.UUID, reason: str):
        e = self.db.get(VolunteerEnrollment, enrollment_id)
        if e is None:
            return None
        e.status = "rejected"
        e.rejection_reason = reason
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dashboard.volunteer.rejected",
                 resource_type="volunteer_enrollment", resource_id=enrollment_id)
        return e

