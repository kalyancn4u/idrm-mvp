"""Dispatch console services — the three-panel data feed."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from shared.audit import log_sync
from shared.enums import (
    DispatchOfferStatus, IncidentStatus, PersonnelStatus, UnitStatus,
)
from shared.models.dispatch import DispatchAssignment, DispatchOffer
from shared.models.identity import User
from shared.models.incident import Incident
from shared.models.organization import Organization
from shared.models.personnel import (
    PersonnelStatusEvent, PersonnelStatusRow, Unit, UnitStatusEvent, UnitStatusRow,
)


class DispatchService:
    def __init__(self, session):
        self.db = session

    # ---- the three panels -------------------------------------------------
    def open_incidents(self, limit: int = 50) -> list[Incident]:
        return list(self.db.execute(
            select(Incident).where(
                Incident.deleted_at.is_(None),
                Incident.status.in_([IncidentStatus.created, IncidentStatus.approved,
                                     IncidentStatus.accepted, IncidentStatus.in_progress]),
            ).order_by(Incident.created_at.asc()).limit(limit)
        ).scalars().all())

    def available_personnel(self, limit: int = 100) -> list[tuple[User, PersonnelStatusRow]]:
        stmt = (
            select(User, PersonnelStatusRow)
            .join(PersonnelStatusRow, PersonnelStatusRow.user_id == User.id)
            .where(User.status == "active",
                   PersonnelStatusRow.status.in_([PersonnelStatus.available,
                                                  PersonnelStatus.responding,
                                                  PersonnelStatus.on_scene]))
            .order_by(PersonnelStatusRow.status.asc())
            .limit(limit)
        )
        return [(u, s) for (u, s) in self.db.execute(stmt).all()]

    def available_units(self, limit: int = 100) -> list[tuple[Unit, UnitStatusRow]]:
        stmt = (
            select(Unit, UnitStatusRow)
            .join(UnitStatusRow, UnitStatusRow.unit_id == Unit.id)
            .where(Unit.deleted_at.is_(None), Unit.is_active.is_(True))
            .order_by(UnitStatusRow.status.asc())
            .limit(limit)
        )
        return [(u, s) for (u, s) in self.db.execute(stmt).all()]

    # ---- actions ----------------------------------------------------------
    def assign(self, incident_id: uuid.UUID, actor_id: uuid.UUID,
               unit_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None,
               note: str | None = None) -> DispatchAssignment:
        now = datetime.now(UTC)
        a = DispatchAssignment(
            incident_id=incident_id, unit_id=unit_id, user_id=user_id,
            assigned_by=actor_id, assigned_at=now, note=note,
        )
        self.db.add(a)

        if unit_id:
            self._set_unit_status(unit_id, UnitStatus.dispatched, actor_id, incident_id)
        if user_id:
            self._set_personnel_status(user_id, PersonnelStatus.responding, actor_id, incident_id)

        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dispatch.assigned",
                 resource_type="incident", resource_id=incident_id,
                 new_values={"unit_id": str(unit_id) if unit_id else None,
                             "user_id": str(user_id) if user_id else None})
        return a

    def offer(self, incident_id: uuid.UUID, actor_id: uuid.UUID,
              unit_id: uuid.UUID | None, user_id: uuid.UUID | None,
              ttl_minutes: int = 15) -> DispatchOffer:
        from datetime import timedelta
        now = datetime.now(UTC)
        o = DispatchOffer(
            incident_id=incident_id, unit_id=unit_id, user_id=user_id,
            offered_by=actor_id, offered_at=now,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )
        self.db.add(o)
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dispatch.offered",
                 resource_type="incident", resource_id=incident_id)
        return o

    def respond(self, offer_id: uuid.UUID, accept: bool, actor_id: uuid.UUID):
        o = self.db.get(DispatchOffer, offer_id)
        if o is None or o.status != DispatchOfferStatus.pending:
            return None
        o.status = DispatchOfferStatus.accepted if accept else DispatchOfferStatus.declined
        o.responded_at = datetime.now(UTC)
        if accept:
            self.assign(o.incident_id, actor_id, o.unit_id, o.user_id, f"Accepted offer {o.id}")
        self.db.flush()
        return o

    def release(self, assignment_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        a = self.db.get(DispatchAssignment, assignment_id)
        if a and a.released_at is None:
            a.released_at = datetime.now(UTC)
            # Free the unit / person, mirroring shared.services.dispatch.release
            if a.unit_id:
                self._set_unit_status(a.unit_id, UnitStatus.in_quarters, actor_id, None)
            if a.user_id:
                self._set_personnel_status(a.user_id, PersonnelStatus.available, actor_id, None)
            self.db.flush()
            log_sync(self.db, actor_id=actor_id, action="dispatch.released",
                     resource_type="dispatch_assignment", resource_id=assignment_id)

    # ---- internal ---------------------------------------------------------
    def _set_unit_status(self, unit_id, status, actor_id, incident_id):
        existing = self.db.execute(
            select(UnitStatusRow).where(UnitStatusRow.unit_id == unit_id)
        ).scalar_one_or_none()
        if existing is None:
            existing = UnitStatusRow(unit_id=unit_id, updated_at=datetime.now(UTC))
            self.db.add(existing)
        from_status = existing.status
        existing.status = status
        existing.incident_id = incident_id
        existing.updated_at = datetime.now(UTC)
        self.db.add(UnitStatusEvent(
            unit_id=unit_id, from_status=from_status, to_status=status,
            incident_id=incident_id, actor_id=actor_id, occurred_at=datetime.now(UTC),
        ))
        self.db.flush()

    def _set_personnel_status(self, user_id, status, actor_id, incident_id):
        existing = self.db.execute(
            select(PersonnelStatusRow).where(PersonnelStatusRow.user_id == user_id)
        ).scalar_one_or_none()
        if existing is None:
            existing = PersonnelStatusRow(user_id=user_id, updated_at=datetime.now(UTC))
            self.db.add(existing)
        from_status = existing.status
        existing.status = status
        existing.updated_at = datetime.now(UTC)
        self.db.add(PersonnelStatusEvent(
            user_id=user_id, from_status=from_status, to_status=status,
            incident_id=incident_id, occurred_at=datetime.now(UTC),
        ))
        self.db.flush()

