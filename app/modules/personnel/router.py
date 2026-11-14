"""Personnel + units router."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import is_staff, is_unit_member
from app.core.dependencies import get_current_claims, get_db, require_role
from app.core.exceptions import AppError
from shared.db import async_session
from shared.enums import PersonnelStatus, UnitStatus
from shared.models.personnel import PersonnelStatusRow, Unit, UnitStatusRow
from shared.services import personnel as personnel_svc
from shared.services import units as units_svc

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Claims = Annotated[dict, Depends(get_current_claims)]


class StatusBody(BaseModel):
    status: PersonnelStatus
    staffing_level: int = 0
    note: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class UnitCreate(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    kind: str | None = None
    callsign: str | None = None
    capacity: int = 1


class UnitStatusBody(BaseModel):
    status: UnitStatus
    incident_id: uuid.UUID | None = None
    latitude: float | None = None
    longitude: float | None = None
    note: str | None = None


# ---- Personnel ---------------------------------------------------------------
@router.get("/personnel/me/status")
async def my_status(db: DbSession, claims: Claims):
    row = (await db.execute(
        select(PersonnelStatusRow).where(PersonnelStatusRow.user_id == uuid.UUID(claims["sub"]))
    )).scalar_one_or_none()
    if row is None:
        return {"status": "off_duty", "staffing_level": 0}
    return {
        "status": row.status.value if hasattr(row.status, "value") else row.status,
        "staffing_level": row.staffing_level,
        "note": row.note,
        "updated_at": row.updated_at.isoformat(),
    }


@router.put("/personnel/me/status")
async def set_my_status(body: StatusBody, db: DbSession, claims: Claims):
    row = await personnel_svc.set_status(
        db, user_id=uuid.UUID(claims["sub"]),
        status=body.status, staffing_level=body.staffing_level, note=body.note,
        latitude=body.latitude, longitude=body.longitude,
    )
    return {
        "status": row.status.value if hasattr(row.status, "value") else row.status,
        "staffing_level": row.staffing_level,
    }


@router.get("/personnel/statuses")
async def list_statuses(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    rows = list((await db.execute(select(PersonnelStatusRow))).scalars().all())
    return {"data": [
        {"user_id": str(r.user_id),
         "status": r.status.value if hasattr(r.status, "value") else r.status,
         "staffing_level": r.staffing_level,
         "updated_at": r.updated_at.isoformat()}
        for r in rows
    ]}


# ---- Units -------------------------------------------------------------------
@router.post("/units")
async def create_unit(
    body: UnitCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    u = await units_svc.create(
        db, organization_id=body.organization_id, name=body.name,
        kind=body.kind, callsign=body.callsign, capacity=body.capacity,
        actor_id=uuid.UUID(claims["sub"]),
    )
    return {"id": str(u.id), "name": u.name}


@router.get("/units")
async def list_units(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin", "provider"))],
):
    rows = list((await db.execute(select(Unit).where(Unit.deleted_at.is_(None)))).scalars().all())
    statuses = {
        r.unit_id: r for r in
        (await db.execute(select(UnitStatusRow))).scalars().all()
    }
    return {"data": [
        {
            "id": str(u.id), "name": u.name, "kind": u.kind,
            "organization_id": str(u.organization_id),
            "status": (statuses[u.id].status.value if hasattr(statuses[u.id].status, "value")
                       else statuses[u.id].status) if u.id in statuses else "in_quarters",
        } for u in rows
    ]}


@router.put("/units/{unit_id}/status")
async def set_unit_status(
    unit_id: uuid.UUID, body: UnitStatusBody, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin", "provider"))],
):
    if not is_staff(claims) and not await is_unit_member(db, uuid.UUID(claims["sub"]), unit_id):
        raise AppError(403, "forbidden", "You are not a member of this unit.")
    row = await units_svc.set_status(
        db, unit_id=unit_id, status=body.status, actor_id=uuid.UUID(claims["sub"]),
        incident_id=body.incident_id, latitude=body.latitude,
        longitude=body.longitude, note=body.note,
    )
    return {"status": row.status.value if hasattr(row.status, "value") else row.status}

