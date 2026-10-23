"""Read-only audit trail."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from shared.models.audit import AuditLog


class AuditService:
    def __init__(self, session):
        self.db = session

    def list(self, *, page: int, limit: int,
             action: str | None = None,
             resource_type: str | None = None):
        conditions = []
        if action:
            conditions.append(AuditLog.action.ilike(f"%{action}%"))
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)

        stmt = select(AuditLog)
        if conditions:
            stmt = stmt.where(*conditions)

        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()
        rows = list(self.db.execute(
            stmt.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * limit).limit(limit)
        ).scalars().all())
        return rows, total

    def distinct_actions(self) -> list[str]:
        return list(self.db.execute(
            select(AuditLog.action).distinct().order_by(AuditLog.action)
        ).scalars().all())

    def distinct_resource_types(self) -> list[str]:
        return list(self.db.execute(
            select(AuditLog.resource_type).where(AuditLog.resource_type.is_not(None))
            .distinct().order_by(AuditLog.resource_type)
        ).scalars().all())

