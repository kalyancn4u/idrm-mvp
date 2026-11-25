"""Dashboard KPI aggregations."""

from __future__ import annotations

from sqlalchemy import func, select

from shared.enums import IncidentStatus
from shared.models.identity import User
from shared.models.incident import Incident
from shared.models.organization import Organization
from shared.models.personnel import PersonnelStatusRow, Unit, UnitStatusRow


class KPIService:
    def __init__(self, session):
        self.db = session

    def summary(self) -> dict:
        db = self.db

        def count(model, *conditions) -> int:
            stmt = select(func.count()).select_from(model)
            if conditions:
                stmt = stmt.where(*conditions)
            return db.execute(stmt).scalar_one()

        # The first card is the coordinator's triage queue: requests still
        # in `created`, waiting for someone to approve or reject them
        # (ADR-0014, ADR-0016). It counts exactly what its link opens.
        waiting = (Incident.status == IncidentStatus.created,
                   Incident.deleted_at.is_(None))

        return {
            "incidents_total": count(Incident, Incident.deleted_at.is_(None)),
            "incidents_awaiting_approval": count(Incident, *waiting),
            "incidents_awaiting_critical": count(Incident, *waiting,
                                                 Incident.priority == "critical"),
            "incidents_verified": count(Incident, Incident.status == IncidentStatus.verified,
                                        Incident.deleted_at.is_(None)),
            "auto_approved": count(Incident, Incident.auto_approved.is_(True),
                                   Incident.deleted_at.is_(None)),
            "orgs_total": count(Organization, Organization.deleted_at.is_(None)),
            "orgs_verified": count(Organization, Organization.is_verified.is_(True),
                                   Organization.deleted_at.is_(None)),
            "users_total": count(User, User.deleted_at.is_(None)),
            "users_active": count(User, User.status == "active", User.deleted_at.is_(None)),
            "units_total": count(Unit, Unit.deleted_at.is_(None)),
            "personnel_available": count(PersonnelStatusRow, PersonnelStatusRow.status == "available"),
            "units_available": count(UnitStatusRow, UnitStatusRow.status == "in_quarters"),
        }

    def incidents_by_status(self) -> list[dict]:
        stmt = (
            select(Incident.status, func.count().label("n"))
            .where(Incident.deleted_at.is_(None))
            .group_by(Incident.status)
            .order_by(func.count().desc())
        )
        return [
            {"status": r.status.value if hasattr(r.status, "value") else r.status, "n": r.n}
            for r in self.db.execute(stmt).all()
        ]

    def incidents_by_service(self) -> list[dict]:
        stmt = (
            select(Incident.service_type, func.count().label("n"))
            .where(Incident.deleted_at.is_(None))
            .group_by(Incident.service_type)
            .order_by(func.count().desc())
        )
        return [
            {"service_type": r.service_type.value if hasattr(r.service_type, "value") else r.service_type,
             "n": r.n}
            for r in self.db.execute(stmt).all()
        ]

    def personnel_by_status(self) -> list[dict]:
        stmt = (
            select(PersonnelStatusRow.status, func.count().label("n"))
            .group_by(PersonnelStatusRow.status)
        )
        return [
            {"status": r.status.value if hasattr(r.status, "value") else r.status, "n": r.n}
            for r in self.db.execute(stmt).all()
        ]

    def units_by_status(self) -> list[dict]:
        stmt = (
            select(UnitStatusRow.status, func.count().label("n"))
            .group_by(UnitStatusRow.status)
        )
        return [
            {"status": r.status.value if hasattr(r.status, "value") else r.status, "n": r.n}
            for r in self.db.execute(stmt).all()
        ]

    def recent_activity(self, limit: int = 12):
        from shared.models.audit import AuditLog

        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

