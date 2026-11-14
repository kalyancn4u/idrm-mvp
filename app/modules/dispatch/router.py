"""Dispatch router — assign, offer, respond, release."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import is_staff, is_unit_member
from app.core.dependencies import get_current_claims, get_db, require_role
from app.core.exceptions import AppError
from shared.db import async_session
from shared.models.dispatch import DispatchAssignment, DispatchOffer
from shared.services import dispatch as dispatch_svc

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Claims = Annotated[dict, Depends(get_current_claims)]


class _Target(BaseModel):
    """Who the incident goes to: a unit, a person, or both — never neither."""

    incident_id: uuid.UUID
    unit_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _needs_a_target(self):
        if self.unit_id is None and self.user_id is None:
            raise ValueError("unit_id or user_id is required")
        return self


class AssignBody(_Target):
    pass


class OfferBody(_Target):
    ttl_minutes: int = Field(default=15, ge=1, le=240)


class RespondBody(BaseModel):
    accept: bool


@router.post("/dispatch/assign")
async def assign(
    body: AssignBody, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    if not body.unit_id and not body.user_id:
        raise AppError(422, "validation_error", "unit_id or user_id is required.")
    a = await dispatch_svc.assign(
        db, incident_id=body.incident_id, unit_id=body.unit_id,
        user_id=body.user_id, actor_id=uuid.UUID(claims["sub"]), note=body.note,
    )
    return {"id": str(a.id), "incident_id": str(a.incident_id)}


@router.post("/dispatch/offer")
async def offer(
    body: OfferBody, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    if not body.unit_id and not body.user_id:
        raise AppError(422, "validation_error", "unit_id or user_id is required.")
    o = await dispatch_svc.offer(
        db, incident_id=body.incident_id, unit_id=body.unit_id,
        user_id=body.user_id, actor_id=uuid.UUID(claims["sub"]),
        ttl_minutes=body.ttl_minutes, note=body.note,
    )
    return {"id": str(o.id), "status": o.status.value}


async def _is_addressee(db: AsyncSession, claims: dict, row) -> bool:
    """Is this offer / assignment addressed to the caller, or to a unit they are on?"""
    uid = uuid.UUID(claims["sub"])
    return row.user_id == uid or await is_unit_member(db, uid, row.unit_id)


@router.post("/dispatch/offers/{offer_id}/respond")
async def respond(offer_id: uuid.UUID, body: RespondBody, db: DbSession, claims: Claims):
    offer_row = await db.get(DispatchOffer, offer_id)
    if offer_row is None:
        raise AppError(404, "not_found", "Offer not found.")
    # Only the person (or a member of the unit) the offer was sent to may answer.
    if not await _is_addressee(db, claims, offer_row):
        raise AppError(403, "forbidden", "This offer was not sent to you.")
    try:
        o = await dispatch_svc.respond(
            db, offer_id=offer_id, accept=body.accept, actor_id=uuid.UUID(claims["sub"]),
        )
    except ValueError as exc:
        # The service may have marked the offer expired; keep that.
        await db.commit()
        raise AppError(409, "conflict", str(exc)) from exc
    return {"id": str(o.id), "status": o.status.value}


@router.post("/dispatch/assignments/{assignment_id}/release")
async def release(
    assignment_id: uuid.UUID, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin", "provider"))],
):
    assignment = await db.get(DispatchAssignment, assignment_id)
    if assignment is None:
        raise AppError(404, "not_found", "Assignment not found.")
    if not is_staff(claims) and not await _is_addressee(db, claims, assignment):
        raise AppError(403, "forbidden", "This assignment is not yours to release.")
    await dispatch_svc.release(db, assignment_id=assignment_id, actor_id=uuid.UUID(claims["sub"]))
    return {"status": "released"}


@router.get("/dispatch/board")
async def board(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    """The Dispatch Console's three-panel data feed."""
    from shared.enums import IncidentStatus
    from shared.models.incident import Incident

    # Open incidents
    open_incidents = list((await db.execute(
        select(Incident).where(
            Incident.deleted_at.is_(None),
            Incident.status.in_([IncidentStatus.created, IncidentStatus.approved,
                                 IncidentStatus.accepted, IncidentStatus.in_progress]),
        ).order_by(Incident.priority.desc(), Incident.created_at.asc())
    )).scalars().all())

    # Active assignments
    active_assignments = list((await db.execute(
        select(DispatchAssignment).where(DispatchAssignment.released_at.is_(None))
    )).scalars().all())

    # Pending offers
    pending_offers = list((await db.execute(
        select(DispatchOffer).where(DispatchOffer.status == "pending")
    )).scalars().all())

    return {
        "incidents": [
            {"id": str(i.id),
             "service_type": i.service_type.value if hasattr(i.service_type, "value") else i.service_type,
             "priority": i.priority.value if hasattr(i.priority, "value") else i.priority,
             "status": i.status.value if hasattr(i.status, "value") else i.status,
             "description": i.description[:200],
             "created_at": i.created_at.isoformat()}
            for i in open_incidents
        ],
        "active_assignments": [
            {"id": str(a.id), "incident_id": str(a.incident_id),
             "unit_id": str(a.unit_id) if a.unit_id else None,
             "user_id": str(a.user_id) if a.user_id else None}
            for a in active_assignments
        ],
        "pending_offers": [
            {"id": str(o.id), "incident_id": str(o.incident_id)}
            for o in pending_offers
        ],
    }

