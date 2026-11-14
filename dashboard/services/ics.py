"""ICS command structure read views."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from shared.models.ics import (
    IncidentCommand,
    IncidentLane,
    LaneAssignment,
    RunLog,
    RunLogEntry,
)


class ICSService:
    def __init__(self, session):
        self.db = session

    def active_command(self, incident_id: uuid.UUID):
        return list(self.db.execute(
            select(IncidentCommand).where(
                IncidentCommand.incident_id == incident_id,
                IncidentCommand.is_active.is_(True),
            )
        ).scalars().all())

    def lanes(self, incident_id: uuid.UUID):
        return list(self.db.execute(
            select(IncidentLane).where(IncidentLane.incident_id == incident_id)
            .order_by(IncidentLane.display_order.asc())
        ).scalars().all())

    def lane_assignments(self, lane_id: uuid.UUID):
        return list(self.db.execute(
            select(LaneAssignment).where(
                LaneAssignment.lane_id == lane_id,
                LaneAssignment.released_at.is_(None),
            )
        ).scalars().all())

    def run_logs_for(self, incident_id: uuid.UUID):
        return list(self.db.execute(
            select(RunLog).where(RunLog.incident_id == incident_id)
            .order_by(RunLog.started_at.desc())
        ).scalars().all())

    def entries_for(self, run_log_id: uuid.UUID):
        return list(self.db.execute(
            select(RunLogEntry).where(RunLogEntry.run_log_id == run_log_id)
            .order_by(RunLogEntry.occurred_at.asc())
        ).scalars().all())

