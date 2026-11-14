"""Shifts, trainings, certifications, calendar — read views."""

from __future__ import annotations

from sqlalchemy import func, select

from shared.models.scheduling import (
    CalendarEvent,
    Certification,
    Shift,
    ShiftSignup,
    Training,
    TrainingAssignment,
)


class SchedulingService:
    def __init__(self, session):
        self.db = session

    def upcoming_shifts(self, limit: int = 50):
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        return list(self.db.execute(
            select(Shift).where(Shift.is_active.is_(True), Shift.ends_at >= now)
            .order_by(Shift.starts_at.asc()).limit(limit)
        ).scalars().all())

    def shift_signups_count(self, shift_id):
        return self.db.execute(
            select(func.count()).select_from(ShiftSignup)
            .where(ShiftSignup.shift_id == shift_id)
        ).scalar_one()

    def trainings(self):
        return list(self.db.execute(select(Training).order_by(Training.title.asc())).scalars().all())

    def training_assignments(self, *, pending_only: bool = True):
        stmt = select(TrainingAssignment)
        if pending_only:
            stmt = stmt.where(TrainingAssignment.status.in_(("assigned", "in_progress")))
        return list(self.db.execute(stmt).scalars().all())

    def certifications(self, *, expiring_days: int = 60):
        from datetime import date, timedelta
        cutoff = date.today() + timedelta(days=expiring_days)
        return list(self.db.execute(
            select(Certification).where(
                Certification.status == "active",
                Certification.expires_at.is_not(None),
                Certification.expires_at <= cutoff,
            ).order_by(Certification.expires_at.asc())
        ).scalars().all())

    def upcoming_events(self, limit: int = 30):
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        return list(self.db.execute(
            select(CalendarEvent).where(CalendarEvent.starts_at >= now)
            .order_by(CalendarEvent.starts_at.asc()).limit(limit)
        ).scalars().all())

