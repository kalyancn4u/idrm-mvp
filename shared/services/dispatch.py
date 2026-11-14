"""
Dispatch service (async, used by the API) — assign units/personnel to
incidents, offer, respond, release.

This file only loads and saves rows. The rules themselves are in
`shared/services/dispatch_core.py`, shared with the staff console.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.audit import log_async
from shared.models.dispatch import DispatchAssignment, DispatchOffer
from shared.models.personnel import PersonnelStatusRow, UnitStatusRow
from shared.notifications import assigned_to_incident
from shared.services import dispatch_core as core


async def assign(
    db: AsyncSession,
    *,
    incident_id: uuid.UUID,
    unit_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    actor_id: uuid.UUID,
    note: str | None = None,
) -> DispatchAssignment:
    """Assign a unit or a person to an incident. Immediate."""
    assignment = core.new_assignment(
        incident_id=incident_id, unit_id=unit_id, user_id=user_id,
        actor_id=actor_id, note=note, now=datetime.now(UTC),
    )
    db.add(assignment)

    if unit_id:
        await _set_unit_status(db, unit_id, core.UNIT_WHEN_ASSIGNED, actor_id, incident_id, "Dispatched")
    if user_id:
        await _set_personnel_status(db, user_id, core.PERSON_WHEN_ASSIGNED, actor_id, incident_id, "Dispatched")
        db.add(assigned_to_incident(user_id=user_id, incident_id=incident_id))

    await db.flush()
    await log_async(
        db,
        actor_id=actor_id,
        action="dispatch.assigned",
        resource_type="incident",
        resource_id=incident_id,
        new_values={
            "unit_id": str(unit_id) if unit_id else None,
            "user_id": str(user_id) if user_id else None,
        },
    )
    return assignment


async def offer(
    db: AsyncSession,
    *,
    incident_id: uuid.UUID,
    unit_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    actor_id: uuid.UUID,
    ttl_minutes: int = core.DEFAULT_OFFER_TTL_MINUTES,
    note: str | None = None,
) -> DispatchOffer:
    """Offer the incident to a unit/person. They must accept."""
    offer_row = core.new_offer(
        incident_id=incident_id, unit_id=unit_id, user_id=user_id,
        actor_id=actor_id, now=datetime.now(UTC), ttl_minutes=ttl_minutes, note=note,
    )
    db.add(offer_row)
    await db.flush()
    await log_async(
        db,
        actor_id=actor_id,
        action="dispatch.offered",
        resource_type="incident",
        resource_id=incident_id,
        new_values={"offer_id": str(offer_row.id)},
    )
    return offer_row


async def respond(
    db: AsyncSession,
    *,
    offer_id: uuid.UUID,
    accept: bool,
    actor_id: uuid.UUID,
) -> DispatchOffer:
    """Answer an offer. Raises `dispatch_core.OfferError` (a ValueError)."""
    offer_row = await db.get(DispatchOffer, offer_id)
    try:
        core.resolve_offer(offer_row, accept=accept, now=datetime.now(UTC))
    except core.OfferError:
        await db.flush()        # keeps the "expired" mark; the caller commits
        raise

    if accept:
        await assign(
            db,
            incident_id=offer_row.incident_id,
            unit_id=offer_row.unit_id,
            user_id=offer_row.user_id,
            actor_id=actor_id,
            note=f"Accepted offer {offer_row.id}",
        )

    await db.flush()
    return offer_row


async def release(
    db: AsyncSession, *, assignment_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    """End an assignment and make the unit / person available again."""
    assignment = await db.get(DispatchAssignment, assignment_id)
    if not core.close_assignment(assignment, now=datetime.now(UTC)):
        return

    if assignment.unit_id:
        await _set_unit_status(db, assignment.unit_id, core.UNIT_WHEN_RELEASED,
                               actor_id, None, "Released")
    if assignment.user_id:
        await _set_personnel_status(db, assignment.user_id, core.PERSON_WHEN_RELEASED,
                                    actor_id, None, "Released")

    await db.flush()
    await log_async(
        db,
        actor_id=actor_id,
        action="dispatch.released",
        resource_type="dispatch_assignment",
        resource_id=assignment_id,
    )


async def _set_unit_status(db, unit_id, status, actor_id, incident_id, note) -> None:
    current = (
        await db.execute(select(UnitStatusRow).where(UnitStatusRow.unit_id == unit_id))
    ).scalar_one_or_none()
    row, event, is_new = core.change_unit_status(
        current, unit_id=unit_id, status=status, actor_id=actor_id,
        incident_id=incident_id, note=note, now=datetime.now(UTC),
    )
    if is_new:
        db.add(row)
    db.add(event)
    await db.flush()


async def _set_personnel_status(db, user_id, status, actor_id, incident_id, note) -> None:
    current = (
        await db.execute(
            select(PersonnelStatusRow).where(PersonnelStatusRow.user_id == user_id)
        )
    ).scalar_one_or_none()
    row, event, is_new = core.change_personnel_status(
        current, user_id=user_id, status=status,
        incident_id=incident_id, note=note, now=datetime.now(UTC),
    )
    if is_new:
        db.add(row)
    db.add(event)
    await db.flush()
