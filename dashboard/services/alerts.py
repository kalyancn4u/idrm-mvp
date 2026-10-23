"""Alerts — create and list."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from shared.audit import log_sync
from shared.models.alert import Alert


class AlertService:
    def __init__(self, session):
        self.db = session

    def list(self, *, page: int, limit: int, active_only: bool = True):
        conditions = [Alert.active.is_(True)] if active_only else []
        stmt = select(Alert)
        if conditions:
            stmt = stmt.where(*conditions)
        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()
        rows = list(self.db.execute(
            stmt.order_by(Alert.created_at.desc())
            .offset((page - 1) * limit).limit(limit)
        ).scalars().all())
        return rows, total

    def create(self, *, title: str, message: str, severity: str, actor_id: uuid.UUID):
        alert = Alert(
            title=title, message=message, severity=severity,
            created_by=actor_id, active=True, created_at=datetime.now(UTC),
        )
        self.db.add(alert)
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dashboard.alert.created",
                 resource_type="alert", resource_id=alert.id,
                 new_values={"title": title, "severity": severity})
        return alert

    def deactivate(self, alert_id: uuid.UUID, actor_id: uuid.UUID):
        alert = self.db.get(Alert, alert_id)
        if alert is None:
            return None
        alert.active = False
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dashboard.alert.deactivated",
                 resource_type="alert", resource_id=alert_id)
        return alert

