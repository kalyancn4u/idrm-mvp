"""
Personnel status service — the responder's "one tap" workflow.

Every status change writes both the current row and an immutable event,
plus an audit entry.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.audit import log_async
from shared.enums import PersonnelStatus
from shared.models.personnel import PersonnelStatusEvent, PersonnelStatusRow


async def set_status(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    status: PersonnelStatus,
    staffing_level: int = 0,
    note: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    incident_id: uuid.UUID | None = None,
    unit_id: uuid.UUID | None = None,
) -> PersonnelStatusRow:
    """Set the caller's operational status. Self-only."""
    existing = (
        await db.execute(
            select(PersonnelStatusRow).where(PersonnelStatusRow.user_id == user_id)
        )
    ).scalar_one_or_none()

    from_status = existing.status if existing else None

    if existing is None:
        existing = PersonnelStatusRow(user_id=user_id)
        db.add(existing)

    existing.status = status
    existing.staffing_level = staffing_level
    existing.note = note
    existing.updated_at = datetime.now(UTC)

    if latitude is not None and longitude is not None:
        from geoalchemy2.elements import WKTElement

        existing.location = WKTElement(f"POINT({longitude} {latitude})", srid=4326)

    db.add(
        PersonnelStatusEvent(
            user_id=user_id,
            from_status=from_status,
            to_status=status,
            staffing_level=staffing_level,
            note=note,
            incident_id=incident_id,
            unit_id=unit_id,
            occurred_at=datetime.now(UTC),
        )
    )
    await db.flush()

    await log_async(
        db,
        actor_id=user_id,
        action="personnel.status_changed",
        resource_type="personnel_status",
        resource_id=user_id,
        old_values={"status": from_status.value if from_status else None},
        new_values={"status": status.value, "staffing_level": staffing_level},
    )
    return existing
