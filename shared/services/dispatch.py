"""
Dispatch service — assign units/personnel to incidents, track response.

Mirrors Resgrid's "dispatcher creates a call, assigns resources,
tracks response" workflow.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.audit import log_async
from shared.enums import DispatchOfferStatus, PersonnelStatus, UnitStatus
from shared.models.dispatch import DispatchAssignment, DispatchOffer
from shared.models.personnel import (
    PersonnelStatusEvent,
    PersonnelStatusRow,
    UnitStatusEvent,
    UnitStatusRow,
)


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
    now = datetime.now(UTC)
    assignment = DispatchAssignment(
        incident_id=incident_id,
        unit_id=unit_id,
        user_id=user_id,
        assigned_by=actor_id,
        assigned_at=now,
        note=note,
    )
    db.add(assignment)

    if unit_id:
        await _set_unit_status(db, unit_id, UnitStatus.dispatched, actor_id, incident_id, "Dispatched")
    if user_id:
        await _set_personnel_status(db, user_id, PersonnelStatus.responding, actor_id, incident_id, "Dispatched")

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
    ttl_minutes: int = 15,
    note: str | None = None,
) -> DispatchOffer:
    """Offer the incident to a unit/person. They must accept."""
    now = datetime.now(UTC)
    offer_row = DispatchOffer(
        incident_id=incident_id,
        unit_id=unit_id,
        user_id=user_id,
        offered_by=actor_id,
        offered_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
        note=note,
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
    offer_row = await db.get(DispatchOffer, offer_id)
    if offer_row is None or offer_row.status != DispatchOfferStatus.pending:
        raise ValueError("Offer not found or already resolved")
    if offer_row.expires_at and offer_row.expires_at < datetime.now(UTC):
        offer_row.status = DispatchOfferStatus.expired
        await db.flush()
        raise ValueError("Offer has expired")

    offer_row.status = (
        DispatchOfferStatus.accepted if accept else DispatchOfferStatus.declined
    )
    offer_row.responded_at = datetime.now(UTC)

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
    if assignment is None or assignment.released_at is not None:
        return
    assignment.released_at = datetime.now(UTC)

    if assignment.unit_id:
        await _set_unit_status(db, assignment.unit_id, UnitStatus.in_quarters,
                               actor_id, None, "Released")
    if assignment.user_id:
        await _set_personnel_status(db, assignment.user_id, PersonnelStatus.available,
                                    actor_id, None, "Released")

    await db.flush()
    await log_async(
        db,
        actor_id=actor_id,
        action="dispatch.released",
        resource_type="dispatch_assignment",
        resource_id=assignment_id,
    )


async def _set_unit_status(
    db, unit_id, status, actor_id, incident_id, note
) -> None:
    existing = (
        await db.execute(select(UnitStatusRow).where(UnitStatusRow.unit_id == unit_id))
    ).scalar_one_or_none()
    if existing is None:
        existing = UnitStatusRow(unit_id=unit_id)
        db.add(existing)
    from_status = existing.status
    existing.status = status
    existing.incident_id = incident_id
    existing.note = note
    existing.updated_at = datetime.now(UTC)
    db.add(
        UnitStatusEvent(
            unit_id=unit_id,
            from_status=from_status,
            to_status=status,
            incident_id=incident_id,
            note=note,
            actor_id=actor_id,
            occurred_at=datetime.now(UTC),
        )
    )
    await db.flush()


async def _set_personnel_status(
    db, user_id, status, actor_id, incident_id, note
) -> None:
    existing = (
        await db.execute(
            select(PersonnelStatusRow).where(PersonnelStatusRow.user_id == user_id)
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = PersonnelStatusRow(user_id=user_id)
        db.add(existing)
    from_status = existing.status
    existing.status = status
    existing.note = note
    existing.updated_at = datetime.now(UTC)
    db.add(
        PersonnelStatusEvent(
            user_id=user_id,
            from_status=from_status,
            to_status=status,
            note=note,
            incident_id=incident_id,
            occurred_at=datetime.now(UTC),
        )
    )
    await db.flush()
