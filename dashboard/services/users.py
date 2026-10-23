"""User read + role/status change."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from shared.audit import log_sync
from shared.models.identity import User, UserSession


class UserService:
    def __init__(self, session):
        self.db = session

    def list(self, *, page: int, limit: int, role: str | None = None,
             status: str | None = None, q: str | None = None):
        conditions = [User.deleted_at.is_(None)]
        if role:
            conditions.append(User.role == role)
        if status:
            conditions.append(User.status == status)
        if q:
            conditions.append(User.name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%"))
        total = self.db.execute(
            select(func.count()).select_from(User).where(*conditions)
        ).scalar_one()
        rows = list(self.db.execute(
            select(User).where(*conditions)
            .order_by(User.created_at.desc())
            .offset((page - 1) * limit).limit(limit)
        ).scalars().all())
        return rows, total

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def set_role(self, user_id: uuid.UUID, role: str, actor_id: uuid.UUID):
        u = self.get(user_id)
        if u is None:
            return None
        old = u.role
        u.role = role
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dashboard.user.role_changed",
                 resource_type="user", resource_id=user_id,
                 old_values={"role": old.value if hasattr(old, "value") else old},
                 new_values={"role": role})
        return u

    def set_status(self, user_id: uuid.UUID, status: str, actor_id: uuid.UUID):
        u = self.get(user_id)
        if u is None:
            return None
        old = u.status
        u.status = status
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dashboard.user.status_changed",
                 resource_type="user", resource_id=user_id,
                 old_values={"status": old.value if hasattr(old, "value") else old},
                 new_values={"status": status})
        return u

    def sessions_for(self, user_id: uuid.UUID):
        return list(self.db.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            ).order_by(UserSession.created_at.desc())
        ).scalars().all())

    def force_logout(self, user_id: uuid.UUID, actor_id: uuid.UUID):
        from datetime import UTC, datetime

        u = self.get(user_id)
        if u is None:
            return None
        u.token_version += 1
        for s in self.sessions_for(user_id):
            s.revoked_at = datetime.now(UTC)
            s.revoked_by = actor_id
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="dashboard.user.force_logout",
                 resource_type="user", resource_id=user_id)
        return u

