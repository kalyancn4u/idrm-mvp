"""ICS command structure, lanes, run logs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_claims, get_db, require_role
from shared.db import async_session
from shared.enums import IcsLaneType, IcsRole
from shared.models.ics import (
    IncidentCommand, IncidentLane, LaneAssignment, RunLog, RunLogEntry,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Claims = Annotated[dict, Depends(get_current_claims)]


class CommandCreate(BaseModel):
    incident_id: uuid.UUID
    commander_id: uuid.UUID
    ics_role: IcsRole = IcsRole.incident_commander
    objectives: str | None = None


class LaneCreate(BaseModel):
    incident_id: uuid.UUID
    lane_type: IcsLaneType
    name: str
    parent_lane_id: uuid.UUID | None = None
    lead_user_id: uuid.UUID | None = None
    objectives: str | None = None


class LaneAssignmentCreate(BaseModel):
    user_id: uuid.UUID | None = None
    unit_id: uuid.UUID | None = None
    role: str | None = None


class RunLogCreate(BaseModel):
    log_type: str
    title: str
    incident_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None
    summary: str | None = None


class RunLogEntryCreate(BaseModel):
    entry_type: str
    description: str
    user_id: uuid.UUID | None = None
    unit_id: uuid.UUID | None = None
    hours: float | None = None


@router.post("/incidents/{incident_id}/command", status_code=status.HTTP_201_CREATED)
async def establish_command(
    incident_id: uuid.UUID, body: CommandCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    cmd = IncidentCommand(
        incident_id=incident_id, commander_id=body.commander_id,
        ics_role=body.ics_role, objectives=body.objectives,
        established_at=datetime.now(UTC),
    )
    db.add(cmd)
    await db.flush()
    return {"id": str(cmd.id)}


@router.get("/incidents/{incident_id}/command")
async def get_command(incident_id: uuid.UUID, db: DbSession, claims: Claims):
    rows = list((await db.execute(
        select(IncidentCommand).where(
            IncidentCommand.incident_id == incident_id,
            IncidentCommand.is_active.is_(True),
        )
    )).scalars().all())
    return {"data": [
        {"id": str(r.id), "commander_id": str(r.commander_id),
         "ics_role": r.ics_role.value if hasattr(r.ics_role, "value") else r.ics_role,
         "objectives": r.objectives}
        for r in rows
    ]}


@router.post("/incidents/{incident_id}/lanes", status_code=status.HTTP_201_CREATED)
async def create_lane(
    incident_id: uuid.UUID, body: LaneCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    lane = IncidentLane(
        incident_id=incident_id, lane_type=body.lane_type, name=body.name,
        parent_lane_id=body.parent_lane_id, lead_user_id=body.lead_user_id,
        objectives=body.objectives, created_at=datetime.now(UTC),
    )
    db.add(lane)
    await db.flush()
    return {"id": str(lane.id), "name": lane.name}


@router.get("/incidents/{incident_id}/lanes")
async def list_lanes(incident_id: uuid.UUID, db: DbSession, claims: Claims):
    rows = list((await db.execute(
        select(IncidentLane).where(IncidentLane.incident_id == incident_id)
        .order_by(IncidentLane.display_order.asc())
    )).scalars().all())
    return {"data": [
        {"id": str(l.id), "name": l.name,
         "lane_type": l.lane_type.value if hasattr(l.lane_type, "value") else l.lane_type,
         "lead_user_id": str(l.lead_user_id) if l.lead_user_id else None,
         "objectives": l.objectives}
        for l in rows
    ]}


@router.post("/incidents/{incident_id}/lanes/{lane_id}/assign", status_code=status.HTTP_201_CREATED)
async def assign_to_lane(
    incident_id: uuid.UUID, lane_id: uuid.UUID, body: LaneAssignmentCreate,
    db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    a = LaneAssignment(
        lane_id=lane_id, user_id=body.user_id, unit_id=body.unit_id,
        role=body.role, assigned_at=datetime.now(UTC),
    )
    db.add(a)
    await db.flush()
    return {"id": str(a.id)}


@router.post("/run-logs", status_code=status.HTTP_201_CREATED)
async def create_run_log(
    body: RunLogCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    rl = RunLog(
        log_type=body.log_type, incident_id=body.incident_id,
        organization_id=body.organization_id, title=body.title,
        summary=body.summary, started_at=datetime.now(UTC),
        created_by=uuid.UUID(claims["sub"]), created_at=datetime.now(UTC),
    )
    db.add(rl)
    await db.flush()
    return {"id": str(rl.id)}


@router.post("/run-logs/{run_log_id}/entries", status_code=status.HTTP_201_CREATED)
async def add_run_log_entry(
    run_log_id: uuid.UUID, body: RunLogEntryCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin", "provider"))],
):
    e = RunLogEntry(
        run_log_id=run_log_id, entry_type=body.entry_type,
        description=body.description, user_id=body.user_id, unit_id=body.unit_id,
        hours=body.hours, occurred_at=datetime.now(UTC),
    )
    db.add(e)
    await db.flush()
    return {"id": str(e.id)}

