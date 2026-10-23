"""Unit management — creation, status, membership."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.audit import log_async
from shared.enums import UnitStatus
from shared.models.personnel import Unit, UnitMember, UnitStatusEvent, UnitStatusRow


async def create(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    name: str,
    kind: str | None,
    callsign: str | None,
    capacity: int,
    actor_id: uuid.UUID,
) -> Unit:
    unit = Unit(
        organization_id=organization_id,
        name=name,
        kind=kind,
        callsign=callsign,
        capacity=capacity,
    )
    db.add(unit)
    await db.flush()
    db.add(UnitStatusRow(unit_id=unit.id, status=UnitStatus.in_quarters, updated_at=datetime.now(UTC)))
    await db.flush()
    await log_async(
        db,
        actor_id=actor_id,
        action="unit.created",
        resource_type="unit",
        resource_id=unit.id,
        new_values={"name": name, "organization_id": str(organization_id)},
    )
    return unit


async def set_status(
    db: AsyncSession,
    *,
    unit_id: uuid.UUID,
    status: UnitStatus,
    actor_id: uuid.UUID,
    incident_id: uuid.UUID | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    note: str | None = None,
) -> UnitStatusRow:
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

    if latitude is not None and longitude is not None:
        from geoalchemy2.elements import WKTElement

        existing.location = WKTElement(f"POINT({longitude} {latitude})", srid=4326)

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
    await log_async(
        db,
        actor_id=actor_id,
        action="unit.status_changed",
        resource_type="unit",
        resource_id=unit_id,
        old_values={"status": from_status.value if from_status else None},
        new_values={"status": status.value},
    )
    return existing


async def add_member(
    db: AsyncSession,
    *,
    unit_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    is_lead: bool,
    actor_id: uuid.UUID,
) -> UnitMember:
    member = UnitMember(
        unit_id=unit_id,
        user_id=user_id,
        role=role,
        is_lead=is_lead,
        joined_at=datetime.now(UTC),
    )
    db.add(member)
    await db.flush()
    await log_async(
        db,
        actor_id=actor_id,
        action="unit.member_added",
        resource_type="unit",
        resource_id=unit_id,
        new_values={"user_id": str(user_id), "role": role},
    )
    return member


async def remove_member(
    db: AsyncSession,
    *,
    unit_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    await db.execute(
        update(UnitMember)
        .where(UnitMember.unit_id == unit_id, UnitMember.user_id == user_id)
        .values(left_at=datetime.now(UTC))
    )
    await db.flush()
    await log_async(
        db,
        actor_id=actor_id,
        action="unit.member_removed",
        resource_type="unit",
        resource_id=unit_id,
        new_values={"user_id": str(user_id)},
    )
