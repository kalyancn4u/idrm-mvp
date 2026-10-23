"""Incident read + coordinator actions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from shared.audit import log_sync
from shared.enums import IncidentStatus
from shared.models.incident import Incident, IncidentUpdate


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

    def coordinator_approve(self, incident_id: uuid.UUID, actor_id: uuid.UUID, note: str | None):
        incident = self.get(incident_id)
        if incident is None:
            return None
        old = incident.status
        incident.status = IncidentStatus.approved
        incident.approved_by = actor_id
        self.db.flush()
        self._add_update(incident_id, old, IncidentStatus.approved, actor_id, note)
        log_sync(self.db, actor_id=actor_id, action="dashboard.incident.approved",
                 resource_type="incident", resource_id=incident_id,
                 new_values={"status": "approved"})
        return incident

    def coordinator_reject(self, incident_id: uuid.UUID, actor_id: uuid.UUID, reason: str):
        incident = self.get(incident_id)
        if incident is None:
            return None
        old = incident.status
        incident.status = IncidentStatus.rejected
        incident.rejection_reason = reason
        self.db.flush()
        self._add_update(incident_id, old, IncidentStatus.rejected, actor_id, reason)
        log_sync(self.db, actor_id=actor_id, action="dashboard.incident.rejected",
                 resource_type="incident", resource_id=incident_id,
                 new_values={"status": "rejected", "reason": reason})
        return incident

    def _add_update(self, incident_id, from_status, to_status, actor_id, note):
        self.db.add(IncidentUpdate(
            incident_id=incident_id, from_status=from_status, to_status=to_status,
            actor_id=actor_id, note=note, created_at=datetime.now(UTC),
        ))
        self.db.flush()

