"""Personnel and units aggregations for the dashboard."""

from __future__ import annotations

from sqlalchemy import select

from shared.models.identity import User
from shared.models.personnel import (
    PersonnelStatusEvent,
    PersonnelStatusRow,
    Unit,
    UnitStatusRow,
)


class PersonnelService:
    def __init__(self, session):
        self.db = session

    def all_with_status(self) -> list[tuple[User, PersonnelStatusRow | None]]:
        stmt = (
            select(User, PersonnelStatusRow)
            .outerjoin(PersonnelStatusRow, PersonnelStatusRow.user_id == User.id)
            .where(User.deleted_at.is_(None),
                   User.role.in_(("provider", "coordinator")))
            .order_by(User.name.asc())
        )
        return [(u, s) for (u, s) in self.db.execute(stmt).all()]

    def all_units(self) -> list[tuple[Unit, UnitStatusRow | None]]:
        stmt = (
            select(Unit, UnitStatusRow)
            .outerjoin(UnitStatusRow, UnitStatusRow.unit_id == Unit.id)
            .where(Unit.deleted_at.is_(None))
            .order_by(Unit.name.asc())
        )
        return [(u, s) for (u, s) in self.db.execute(stmt).all()]

    def recent_status_events(self, limit: int = 20):
        return list(self.db.execute(
            select(PersonnelStatusEvent)
            .order_by(PersonnelStatusEvent.occurred_at.desc())
            .limit(limit)
        ).scalars().all())

