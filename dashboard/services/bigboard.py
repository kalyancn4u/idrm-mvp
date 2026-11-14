"""BigBoard widget data provider — one call per widget type."""

from __future__ import annotations

from sqlalchemy import func, select

from shared.enums import IncidentStatus
from shared.models.identity import User
from shared.models.incident import Incident
from shared.models.organization import Organization
from shared.models.personnel import PersonnelStatusRow, Unit, UnitStatusRow
from shared.models.scheduling import Shift, ShiftSignup


class BigBoardService:
    def __init__(self, session):
        self.db = session

    def widgets(self, widget_types: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for w in widget_types:
            handler = getattr(self, f"widget_{w}", None)
            if handler:
                try:
                    out[w] = handler()
                except Exception as exc:
                    out[w] = {"error": str(exc)}
        return out

    # ---- widget providers -------------------------------------------------
    def widget_active_incidents(self, limit: int = 8) -> dict:
        rows = list(self.db.execute(
            select(Incident).where(
                Incident.deleted_at.is_(None),
                Incident.status.in_([IncidentStatus.created, IncidentStatus.approved,
                                     IncidentStatus.accepted, IncidentStatus.in_progress]),
            ).order_by(Incident.priority.desc(), Incident.created_at.asc()).limit(limit)
        ).scalars().all())
        return {"items": [
            {"id": str(i.id),
             "service": i.service_type.value if hasattr(i.service_type, "value") else i.service_type,
             "priority": i.priority.value if hasattr(i.priority, "value") else i.priority,
             "status": i.status.value if hasattr(i.status, "value") else i.status,
             "description": i.description[:80],
             "created_at": i.created_at.isoformat()}
            for i in rows
        ]}

    def widget_personnel_summary(self) -> dict:
        rows = self.db.execute(
            select(PersonnelStatusRow.status, func.count().label("n"))
            .group_by(PersonnelStatusRow.status)
        ).all()
        return {"counts": [
            {"status": r.status.value if hasattr(r.status, "value") else r.status, "n": r.n}
            for r in rows
        ]}

    def widget_unit_summary(self) -> dict:
        rows = self.db.execute(
            select(UnitStatusRow.status, func.count().label("n"))
            .group_by(UnitStatusRow.status)
        ).all()
        return {"counts": [
            {"status": r.status.value if hasattr(r.status, "value") else r.status, "n": r.n}
            for r in rows
        ]}

    def widget_orgs_summary(self) -> dict:
        total = self.db.execute(select(func.count()).select_from(Organization)
                                .where(Organization.deleted_at.is_(None))).scalar_one()
        verified = self.db.execute(select(func.count()).select_from(Organization)
                                   .where(Organization.is_verified.is_(True),
                                          Organization.deleted_at.is_(None))).scalar_one()
        available = self.db.execute(select(func.count()).select_from(Organization)
                                    .where(Organization.is_available.is_(True),
                                           Organization.deleted_at.is_(None))).scalar_one()
        return {"total": total, "verified": verified, "available": available}

    def widget_shift_coverage(self, limit: int = 6) -> dict:
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        rows = list(self.db.execute(
            select(Shift).where(Shift.is_active.is_(True), Shift.starts_at >= now)
            .order_by(Shift.starts_at.asc()).limit(limit)
        ).scalars().all())
        out = []
        for s in rows:
            signups = self.db.execute(
                select(func.count()).select_from(ShiftSignup)
                .where(ShiftSignup.shift_id == s.id)
            ).scalar_one()
            out.append({
                "id": str(s.id), "name": s.name,
                "starts_at": s.starts_at.isoformat(),
                "min": s.min_personnel, "signed_up": signups,
            })
        return {"items": out}

    def widget_available_resources(self, limit: int = 20) -> dict:
        units = list(self.db.execute(
            select(Unit).where(Unit.deleted_at.is_(None), Unit.is_active.is_(True))
            .limit(limit)
        ).scalars().all())
        statuses = {
            r.unit_id: r for r in self.db.execute(select(UnitStatusRow)).scalars().all()
        }
        return {"items": [
            {"id": str(u.id), "name": u.name,
             "status": (statuses[u.id].status.value
                        if u.id in statuses and hasattr(statuses[u.id].status, "value")
                        else statuses[u.id].status if u.id in statuses else "in_quarters")}
            for u in units
        ]}

