"""Dispatch console services — the three-panel data feed."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from shared.audit import log_sync
from shared.enums import (
    IncidentStatus,
    PersonnelStatus,
)
from shared.models.dispatch import DispatchAssignment, DispatchOffer
from shared.models.identity import User
from shared.models.incident import Incident
from shared.models.personnel import (
    PersonnelStatusRow,
    Unit,
    UnitStatusRow,
)
from shared.notifications import assigned_to_incident
from shared.services import dispatch_core as core


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
    # Load and save only. The rules are in shared/services/dispatch_core.py,
    # shared with the API, so the console and the API cannot disagree.
    def assign(self, incident_id: uuid.UUID, actor_id: uuid.UUID,
               unit_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None,
               note: str | None = None) -> DispatchAssignment:
        a = core.new_assignment(
            incident_id=incident_id, unit_id=unit_id, user_id=user_id,
            actor_id=actor_id, note=note, now=datetime.now(UTC),
        )
        self.db.add(a)

        if unit_id:
            self._set_unit_status(unit_id, core.UNIT_WHEN_ASSIGNED, actor_id, incident_id, "Dispatched")
        if user_id:
            self._set_personnel_status(user_id, core.PERSON_WHEN_ASSIGNED, actor_id, incident_id, "Dispatched")
            self.db.add(assigned_to_incident(user_id=user_id, incident_id=incident_id))

        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dispatch.assigned",
                 resource_type="incident", resource_id=incident_id,
                 new_values={"unit_id": str(unit_id) if unit_id else None,
                             "user_id": str(user_id) if user_id else None})
        return a

    def offer(self, incident_id: uuid.UUID, actor_id: uuid.UUID,
              unit_id: uuid.UUID | None, user_id: uuid.UUID | None,
              ttl_minutes: int = core.DEFAULT_OFFER_TTL_MINUTES) -> DispatchOffer:
        o = core.new_offer(
            incident_id=incident_id, unit_id=unit_id, user_id=user_id,
            actor_id=actor_id, now=datetime.now(UTC), ttl_minutes=ttl_minutes,
        )
        self.db.add(o)
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dispatch.offered",
                 resource_type="incident", resource_id=incident_id,
                 new_values={"offer_id": str(o.id)})
        return o

    def respond(self, offer_id: uuid.UUID, accept: bool, actor_id: uuid.UUID) -> DispatchOffer:
        """Answer an offer. Raises `dispatch_core.OfferError` (a ValueError)."""
        o = self.db.get(DispatchOffer, offer_id)
        try:
            core.resolve_offer(o, accept=accept, now=datetime.now(UTC))
        except core.OfferError:
            self.db.flush()
            raise
        if accept:
            self.assign(o.incident_id, actor_id, o.unit_id, o.user_id, f"Accepted offer {o.id}")
        self.db.flush()
        return o

    def release(self, assignment_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        a = self.db.get(DispatchAssignment, assignment_id)
        if not core.close_assignment(a, now=datetime.now(UTC)):
            return
        if a.unit_id:
            self._set_unit_status(a.unit_id, core.UNIT_WHEN_RELEASED, actor_id, None, "Released")
        if a.user_id:
            self._set_personnel_status(a.user_id, core.PERSON_WHEN_RELEASED, actor_id, None, "Released")
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dispatch.released",
                 resource_type="dispatch_assignment", resource_id=assignment_id)

    # ---- internal ---------------------------------------------------------
    def _set_unit_status(self, unit_id, status, actor_id, incident_id, note=None):
        current = self.db.execute(
            select(UnitStatusRow).where(UnitStatusRow.unit_id == unit_id)
        ).scalar_one_or_none()
        row, event, is_new = core.change_unit_status(
            current, unit_id=unit_id, status=status, actor_id=actor_id,
            incident_id=incident_id, note=note, now=datetime.now(UTC),
        )
        if is_new:
            self.db.add(row)
        self.db.add(event)
        self.db.flush()

    def _set_personnel_status(self, user_id, status, actor_id, incident_id, note=None):
        current = self.db.execute(
            select(PersonnelStatusRow).where(PersonnelStatusRow.user_id == user_id)
        ).scalar_one_or_none()
        row, event, is_new = core.change_personnel_status(
            current, user_id=user_id, status=status,
            incident_id=incident_id, note=note, now=datetime.now(UTC),
        )
        if is_new:
            self.db.add(row)
        self.db.add(event)
        self.db.flush()
