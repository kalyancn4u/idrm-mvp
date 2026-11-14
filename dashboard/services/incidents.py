"""Incident read + coordinator actions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from shared.audit import log_sync
from shared.enums import IncidentStatus
from shared.lifecycle import can_transition, next_status
from shared.models.incident import Incident, IncidentUpdate
from shared.notifications import incident_status_changed


class IncidentService:
    def __init__(self, session):
        self.db = session

    def list(
        self,
        *,
        page: int,
        limit: int,
        status: str | None = None,
        service_type: str | None = None,
        priority: str | None = None,
        q: str | None = None,
    ) -> tuple[list[Incident], int]:
        conditions = [Incident.deleted_at.is_(None)]
        if status:
            conditions.append(Incident.status == status)
        if service_type:
            conditions.append(Incident.service_type == service_type)
        if priority:
            conditions.append(Incident.priority == priority)
        if q:
            conditions.append(Incident.description.ilike(f"%{q}%"))

        total = self.db.execute(
            select(func.count()).select_from(Incident).where(*conditions)
        ).scalar_one()

        rows = list(self.db.execute(
            select(Incident).where(*conditions)
            .order_by(Incident.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        ).scalars().all())
        return rows, total

    def get(self, incident_id: uuid.UUID) -> Incident | None:
        return self.db.get(Incident, incident_id)

    def updates_for(self, incident_id: uuid.UUID) -> list[IncidentUpdate]:
        stmt = (
            select(IncidentUpdate)
            .where(IncidentUpdate.incident_id == incident_id)
            .order_by(IncidentUpdate.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def _transition(self, incident_id: uuid.UUID, action: str) -> tuple[Incident, IncidentStatus]:
        """
        Load the incident (locked) and check `action` is legal from its state.

        Raises ValueError with a message fit to show the coordinator.
        """
        incident = self.db.get(Incident, incident_id, with_for_update=True)
        if incident is None or incident.deleted_at is not None:
            raise ValueError("Incident not found.")
        current = incident.status if isinstance(incident.status, IncidentStatus) else IncidentStatus(incident.status)
        if not can_transition(action, current):
            raise ValueError(f"Cannot {action} an incident that is '{current.value}'.")
        return incident, current

    def coordinator_approve(self, incident_id: uuid.UUID, actor_id: uuid.UUID, note: str | None):
        incident, old = self._transition(incident_id, "approve")
        incident.status = next_status("approve")
        incident.approved_by = actor_id
        self.db.flush()
        self._add_update(incident_id, old, incident.status, actor_id, note)
        self._notify(incident, actor_id)
        log_sync(self.db, actor_id=actor_id, action="dashboard.incident.approved",
                 resource_type="incident", resource_id=incident_id,
                 old_values={"status": old.value},
                 new_values={"status": "approved"})
        return incident

    def coordinator_reject(self, incident_id: uuid.UUID, actor_id: uuid.UUID, reason: str):
        incident, old = self._transition(incident_id, "reject")
        incident.status = next_status("reject")
        incident.rejection_reason = reason
        self.db.flush()
        self._add_update(incident_id, old, incident.status, actor_id, reason)
        self._notify(incident, actor_id, reason)
        log_sync(self.db, actor_id=actor_id, action="dashboard.incident.rejected",
                 resource_type="incident", resource_id=incident_id,
                 old_values={"status": old.value},
                 new_values={"status": "rejected", "reason": reason})
        return incident

    def _notify(self, incident: Incident, actor_id: uuid.UUID, reason: str | None = None) -> None:
        row = incident_status_changed(
            requester_id=incident.requester_id, actor_id=actor_id,
            incident_id=incident.id, new_status=incident.status, reason=reason,
        )
        if row:
            self.db.add(row)

    def _add_update(self, incident_id, from_status, to_status, actor_id, note):
        self.db.add(IncidentUpdate(
            incident_id=incident_id, from_status=from_status, to_status=to_status,
            actor_id=actor_id, note=note, created_at=datetime.now(UTC),
        ))
        self.db.flush()

