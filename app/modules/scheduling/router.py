"""Scheduling — shifts, signups, trainings, calendar."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_claims, get_db, require_role
from app.core.exceptions import AppError
from shared.db import async_session
from shared.enums import ShiftType
from shared.models.scheduling import (
    CalendarEvent, Shift, ShiftSignup, Training, TrainingAssignment,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Claims = Annotated[dict, Depends(get_current_claims)]


class ShiftCreate(BaseModel):
    organization_id: uuid.UUID
    name: str
    starts_at: datetime
    ends_at: datetime
    min_personnel: int = 1
    max_personnel: int | None = None
    required_roles: list[str] = []
    required_certs: list[str] = []
    notes: str | None = None


class TrainingCreate(BaseModel):
    organization_id: uuid.UUID
    code: str
    title: str
    description: str | None = None
    content: str | None = None
    passing_score: int | None = None
    validity_months: int | None = None


class TrainingAssignBody(BaseModel):
    user_ids: list[uuid.UUID]
    due_at: datetime | None = None


class EventCreate(BaseModel):
    organization_id: uuid.UUID
    title: str
    description: str | None = None
    event_type: str | None = None
    starts_at: datetime
    ends_at: datetime
    rsvp_required: bool = False


# ---- Shifts -------------------------------------------------------------------
@router.post("/shifts", status_code=status.HTTP_201_CREATED)
async def create_shift(
    body: ShiftCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    shift = Shift(
        organization_id=body.organization_id, name=body.name,
        shift_type=ShiftType.signup,
        starts_at=body.starts_at, ends_at=body.ends_at,
        min_personnel=body.min_personnel, max_personnel=body.max_personnel,
        required_roles=body.required_roles, required_certs=body.required_certs,
        notes=body.notes, created_by=uuid.UUID(claims["sub"]),
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    db.add(shift)
    await db.flush()
    return {"id": str(shift.id), "name": shift.name}


@router.get("/shifts")
async def list_shifts(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin", "provider"))],
    organization_id: uuid.UUID | None = None,
):
    stmt = select(Shift).where(Shift.is_active.is_(True))
    if organization_id:
        stmt = stmt.where(Shift.organization_id == organization_id)
    rows = list((await db.execute(stmt.order_by(Shift.starts_at.asc()))).scalars().all())
    return {"data": [
        {"id": str(s.id), "name": s.name, "starts_at": s.starts_at.isoformat(),
         "ends_at": s.ends_at.isoformat(), "min_personnel": s.min_personnel}
        for s in rows
    ]}


@router.post("/shifts/{shift_id}/signup", status_code=status.HTTP_201_CREATED)
async def signup(shift_id: uuid.UUID, db: DbSession, claims: Claims):
    existing = (await db.execute(
        select(ShiftSignup).where(
            ShiftSignup.shift_id == shift_id,
            ShiftSignup.user_id == uuid.UUID(claims["sub"]),
        )
    )).scalar_one_or_none()
    if existing:
        raise AppError(409, "conflict", "You are already signed up for this shift.")
    signup = ShiftSignup(
        shift_id=shift_id, user_id=uuid.UUID(claims["sub"]),
        signed_up_at=datetime.now(UTC),
    )
    db.add(signup)
    await db.flush()
    return {"id": str(signup.id)}


# ---- Trainings ----------------------------------------------------------------
@router.post("/trainings", status_code=status.HTTP_201_CREATED)
async def create_training(
    body: TrainingCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    t = Training(
        organization_id=body.organization_id, code=body.code, title=body.title,
        description=body.description, content=body.content,
        passing_score=body.passing_score, validity_months=body.validity_months,
        created_by=uuid.UUID(claims["sub"]),
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    db.add(t)
    await db.flush()
    return {"id": str(t.id), "code": t.code}


@router.post("/trainings/{training_id}/assign")
async def assign_training(
    training_id: uuid.UUID, body: TrainingAssignBody, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    created = []
    for uid in body.user_ids:
        existing = (await db.execute(
            select(TrainingAssignment).where(
                TrainingAssignment.training_id == training_id,
                TrainingAssignment.user_id == uid,
            )
        )).scalar_one_or_none()
        if existing:
            continue
        a = TrainingAssignment(
            training_id=training_id, user_id=uid, due_at=body.due_at,
            status="assigned", assigned_at=datetime.now(UTC),
            assigned_by=uuid.UUID(claims["sub"]),
        )
        db.add(a)
        created.append(a)
    # Ids are generated by the database, so they exist only after the flush.
    await db.flush()
    return {"assigned": [str(a.id) for a in created]}


# ---- Calendar -----------------------------------------------------------------
@router.post("/calendar", status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    e = CalendarEvent(
        organization_id=body.organization_id, title=body.title,
        description=body.description, event_type=body.event_type,
        starts_at=body.starts_at, ends_at=body.ends_at,
        rsvp_required=body.rsvp_required,
        created_by=uuid.UUID(claims["sub"]), created_at=datetime.now(UTC),
    )
    db.add(e)
    await db.flush()
    return {"id": str(e.id), "title": e.title}

