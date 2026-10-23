"""Incidents router — create, list, lifecycle transitions, ICS integration."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from geoalchemy2.elements import WKTElement
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_claims, get_db, get_optional_claims, require_role,
)
from app.core.exceptions import AppError
from app.core.pagination import clamp_limit, paginate
from app.modules.incidents.lifecycle import can_transition, next_status, role_allowed
from shared.audit import log_async
from shared.db import async_session
from shared.enums import AppliesTo, IncidentStatus, Priority, ServiceType
from shared.governance import entity_lists, evaluator
from shared.models.identity import User
from shared.models.incident import Incident, IncidentUpdate
from shared.rate_limit import rate_limit

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Claims = Annotated[dict, Depends(get_current_claims)]
OptClaims = Annotated[dict | None, Depends(get_optional_claims)]


# ---- Schemas -----------------------------------------------------------------
class LatLng(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class IncidentCreate(BaseModel):
    service_type: ServiceType
    priority: Priority
    description: str = Field(min_length=10, max_length=4000)
    location: LatLng
    guest_contact: str | None = Field(default=None, max_length=20)


class IncidentPatch(BaseModel):
    description: str | None = Field(default=None, min_length=10)
    priority: Priority | None = None


def _point(lat: float, lng: float) -> WKTElement:
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


def _to_response(i: Incident) -> dict:
    lat = lng = None
    if i.location is not None:
        try:
            from geoalchemy2.shape import to_shape
            pt = to_shape(i.location)
            lat, lng = pt.y, pt.x
        except Exception:
            pass
    return {
        "id": str(i.id),
        "service_type": i.service_type.value if hasattr(i.service_type, "value") else i.service_type,
        "priority": i.priority.value if hasattr(i.priority, "value") else i.priority,
        "status": i.status.value if hasattr(i.status, "value") else i.status,
        "description": i.description,
        "latitude": lat,
        "longitude": lng,
        "requester_id": str(i.requester_id) if i.requester_id else None,
        "assigned_organization_id": str(i.assigned_organization_id) if i.assigned_organization_id else None,
        "auto_approved": i.auto_approved,
        "rating": i.rating,
        "review": i.review,
        "tracking_token": i.tracking_token,
        "created_at": i.created_at.isoformat(),
        "updated_at": i.updated_at.isoformat(),
    }


async def _add_update(db, incident_id, from_status, to_status, actor_id, note):
    db.add(IncidentUpdate(
        incident_id=incident_id, from_status=from_status, to_status=to_status,
        actor_id=actor_id, note=note, created_at=datetime.now(UTC),
    ))
    await db.flush()


# ---- Endpoints ---------------------------------------------------------------
@router.post("/incidents", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit("incident_create", limit=20))])
async def create_incident(data: IncidentCreate, db: DbSession, claims: OptClaims):
    requester_id = uuid.UUID(claims["sub"]) if claims else None
    if claims and claims.get("role") == "provider":
        raise AppError(403, "forbidden", "Providers cannot raise help requests.")

    # Entity list check on the requester's email (if logged in)
    if claims:
        user = await db.get(User, requester_id)
        check = await entity_lists.evaluate(
            db, subject_user_id=requester_id, entity_type="email",
            value=user.email if user else "", context={"endpoint": "incident.create"},
        )
        if not check["allowed"]:
            raise AppError(403, "forbidden", "Your account is blocked from creating requests.")

    incident = Incident(
        service_type=data.service_type,
        priority=data.priority,
        status=IncidentStatus.created,
        description=data.description,
        location=_point(data.location.latitude, data.location.longitude),
        requester_id=requester_id,
        guest_contact=data.guest_contact if requester_id is None else None,
        tracking_token=secrets.token_urlsafe(24) if requester_id is None else None,
    )
    db.add(incident)
    await db.flush()

    await _add_update(db, incident.id, None, IncidentStatus.created, requester_id, "Request created.")
    await log_async(db, actor_id=requester_id, action="incident.created",
                    resource_type="incident", resource_id=incident.id,
                    new_values={"service_type": data.service_type.value,
                                "priority": data.priority.value})

    # Auto-approval
    decision = await evaluator.decide(
        db,
        subject_type=AppliesTo.incident.value,
        subject_id=incident.id,
        facts={
            "latitude": data.location.latitude,
            "longitude": data.location.longitude,
            "service_type": data.service_type.value,
            "priority": data.priority.value,
            "requester_id": requester_id,
            "requester_trust_score": 0,
        },
    )
    if decision.decision.value == "approved":
        incident.status = IncidentStatus.approved
        incident.auto_approved = True
        incident.auto_policy_id = decision.policy_id
        await _add_update(db, incident.id, IncidentStatus.created, IncidentStatus.approved, None,
                          f"Auto-approved by policy {decision.policy_id}")
        await log_async(db, actor_id=None, action="incident.auto_approved",
                        resource_type="incident", resource_id=incident.id)

    await db.flush()
    return _to_response(incident)


@router.get("/incidents")
async def list_incidents(
    db: DbSession,
    claims: Claims,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    service_type: str | None = None,
    priority: str | None = None,
    q: str | None = None,
):
    role = claims.get("role")
    uid = uuid.UUID(claims["sub"])

    conditions = [Incident.deleted_at.is_(None)]
    if role == "citizen":
        conditions.append(Incident.requester_id == uid)
    if status_filter:
        conditions.append(Incident.status == status_filter)
    if service_type:
        conditions.append(Incident.service_type == service_type)
    if priority:
        conditions.append(Incident.priority == priority)
    if q:
        conditions.append(
            func.to_tsvector("english", Incident.description).op("@@")(
                func.plainto_tsquery("english", q))
        )

    total = (await db.execute(
        select(func.count()).select_from(Incident).where(*conditions)
    )).scalar_one()

    rows = list((await db.execute(
        select(Incident).where(*conditions)
        .order_by(Incident.created_at.desc())
        .offset((page - 1) * clamp_limit(limit))
        .limit(clamp_limit(limit))
    )).scalars().all())

    return paginate([_to_response(i) for i in rows], total, page, clamp_limit(limit))


@router.get("/incidents/mine")
async def my_incidents(
    db: DbSession,
    claims: Annotated[dict, Depends(require_role("citizen", "admin"))],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    conditions = [Incident.requester_id == uuid.UUID(claims["sub"]),
                  Incident.deleted_at.is_(None)]
    total = (await db.execute(
        select(func.count()).select_from(Incident).where(*conditions)
    )).scalar_one()
    rows = list((await db.execute(
        select(Incident).where(*conditions)
        .order_by(Incident.created_at.desc())
        .offset((page - 1) * clamp_limit(limit))
        .limit(clamp_limit(limit))
    )).scalars().all())
    return paginate([_to_response(i) for i in rows], total, page, clamp_limit(limit))


@router.get("/incidents/track/{token}")
async def track_guest(token: str, db: DbSession):
    incident = (await db.execute(
        select(Incident).where(Incident.tracking_token == token)
    )).scalar_one_or_none()
    if incident is None:
        raise AppError(404, "not_found", "No request matches that tracking token.")
    return _to_response(incident)


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: uuid.UUID, db: DbSession, claims: OptClaims):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise AppError(404, "not_found", "Incident not found.")
    if claims is None:
        raise AppError(401, "unauthorized", "Authentication required.")
    role = claims.get("role")
    uid = uuid.UUID(claims["sub"])
    if role in ("coordinator", "admin", "provider"):
        return _to_response(incident)
    if role == "citizen" and incident.requester_id == uid:
        return _to_response(incident)
    raise AppError(403, "forbidden", "You may not view this request.")


@router.get("/incidents/{incident_id}/updates")
async def get_updates(incident_id: uuid.UUID, db: DbSession, claims: Claims):
    rows = list((await db.execute(
        select(IncidentUpdate).where(IncidentUpdate.incident_id == incident_id)
        .order_by(IncidentUpdate.created_at.asc())
    )).scalars().all())
    return {"data": [
        {"id": str(r.id),
         "from_status": r.from_status.value if r.from_status else None,
         "to_status": r.to_status.value,
         "actor_id": str(r.actor_id) if r.actor_id else None,
         "note": r.note,
         "created_at": r.created_at.isoformat()}
        for r in rows
    ]}


async def _do_transition(
    db: AsyncSession, incident_id: uuid.UUID, action: str, claims: dict, payload: dict,
) -> Incident:
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise AppError(404, "not_found", "Incident not found.")

    role = claims.get("role")
    actor_id = uuid.UUID(claims["sub"])

    if not role_allowed(action, role):
        raise AppError(403, "forbidden", f"Role '{role}' may not {action}.")

    current = incident.status if isinstance(incident.status, IncidentStatus) else IncidentStatus(incident.status)

    if not can_transition(action, current):
        raise AppError(409, "invalid_transition",
                       f"Cannot {action} from '{current.value}'.",
                       details={"current_status": current.value})

    if action == "accept" and incident.assigned_organization_id is not None:
        raise AppError(409, "already_accepted", "This request has already been claimed.")

    if action == "verify" and incident.requester_id != actor_id:
        raise AppError(403, "forbidden", "Only the requester may verify.")

    new_status = next_status(action)
    old_status = current

    incident.status = new_status
    if action == "reject":
        incident.rejection_reason = payload.get("reason")
    if action == "cancel":
        incident.cancellation_reason = payload.get("reason")
    if action == "verify":
        incident.rating = payload.get("rating")
        incident.review = payload.get("review")
        incident.verified_at = datetime.now(UTC)
    if action == "approve":
        incident.approved_by = actor_id

    await _add_update(db, incident.id, old_status, new_status, actor_id,
                      payload.get("note") or payload.get("reason"))
    await log_async(db, actor_id=actor_id, action=f"incident.{action}",
                    resource_type="incident", resource_id=incident.id,
                    old_values={"status": old_status.value},
                    new_values={"status": new_status.value})
    await db.flush()
    return incident


class Body(BaseModel):
    note: str | None = None
    reason: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    review: str | None = None
    eta: str | None = None
    notes: str | None = None
    organization_id: uuid.UUID | None = None


@router.post("/incidents/{incident_id}/approve")
async def approve(incident_id: uuid.UUID, body: Body, db: DbSession, claims: Claims):
    return _to_response(await _do_transition(db, incident_id, "approve", claims, body.model_dump()))


@router.post("/incidents/{incident_id}/reject")
async def reject(incident_id: uuid.UUID, body: Body, db: DbSession, claims: Claims):
    return _to_response(await _do_transition(db, incident_id, "reject", claims, body.model_dump()))


@router.post("/incidents/{incident_id}/accept")
async def accept(incident_id: uuid.UUID, body: Body, db: DbSession, claims: Claims):
    return _to_response(await _do_transition(db, incident_id, "accept", claims, body.model_dump()))


@router.post("/incidents/{incident_id}/start")
async def start(incident_id: uuid.UUID, db: DbSession, claims: Claims):
    return _to_response(await _do_transition(db, incident_id, "start", claims, {}))


@router.post("/incidents/{incident_id}/complete")
async def complete(incident_id: uuid.UUID, body: Body, db: DbSession, claims: Claims):
    return _to_response(await _do_transition(db, incident_id, "complete", claims, body.model_dump()))


@router.post("/incidents/{incident_id}/verify")
async def verify(incident_id: uuid.UUID, body: Body, db: DbSession, claims: Claims):
    return _to_response(await _do_transition(db, incident_id, "verify", claims, body.model_dump()))


@router.post("/incidents/{incident_id}/cancel")
async def cancel(incident_id: uuid.UUID, body: Body, db: DbSession, claims: Claims):
    return _to_response(await _do_transition(db, incident_id, "cancel", claims, body.model_dump()))


@router.get("/incidents/nearby")
async def nearby_incidents(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("provider", "coordinator", "admin"))],
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10, gt=0, le=200),
    service_type: str | None = None,
):
    conditions = [
        Incident.deleted_at.is_(None),
        Incident.status.in_([IncidentStatus.created, IncidentStatus.approved,
                             IncidentStatus.accepted, IncidentStatus.in_progress]),
        text(
            "ST_DWithin(location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), :r)"
        ),
    ]
    params = {"lng": longitude, "lat": latitude, "r": radius_km * 1000}
    if service_type:
        conditions.append(Incident.service_type == service_type)

    stmt = select(Incident).where(*conditions).limit(100)
    rows = list((await db.execute(stmt, params)).scalars().all())
    return {"data": [_to_response(i) for i in rows]}

