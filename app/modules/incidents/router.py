"""Incidents router — create, list, lifecycle transitions, ICS integration."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from geoalchemy2.elements import WKTElement
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import is_org_member, member_org_ids
from app.core.dependencies import (
    get_current_claims,
    get_db,
    get_optional_claims,
    rate_limit,
    require_role,
)
from app.core.exceptions import AppError
from app.core.pagination import clamp_limit, paginate
from shared.audit import log_async
from shared.enums import AppliesTo, IncidentStatus, Priority, ServiceType
from shared.geo import point_lat_lng
from shared.governance import entity_lists, evaluator
from shared.governance.regions import find_region
from shared.lifecycle import can_transition, next_status, role_allowed
from shared.models.identity import User
from shared.models.incident import Incident, IncidentUpdate
from shared.notifications import incident_status_changed

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
    lat, lng = point_lat_lng(i.location)
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
    trust_score = 0

    # Entity list check on the requester's email (if logged in)
    if claims:
        user = await db.get(User, requester_id)
        check = await entity_lists.evaluate(
            db, subject_user_id=requester_id, entity_type="email",
            value=user.email if user else "", context={"endpoint": "incident.create"},
        )
        if not check["allowed"]:
            raise AppError(403, "forbidden", "Your account is blocked from creating requests.")
        trust_score = user.trust_score if user else 0

    # Which region is this point in? Stored on the incident so reports and
    # region-based views can find it.
    region = await find_region(db, data.location.latitude, data.location.longitude)

    incident = Incident(
        service_type=data.service_type,
        priority=data.priority,
        status=IncidentStatus.created,
        description=data.description,
        location=_point(data.location.latitude, data.location.longitude),
        region_id=uuid.UUID(str(region["id"])) if region else None,
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
            "requester_trust_score": trust_score,
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
        note = incident_status_changed(requester_id=requester_id, actor_id=None,
                                       incident_id=incident.id, new_status=IncidentStatus.approved)
        if note:
            db.add(note)

    await db.flush()
    return _to_response(incident)


@router.get("/incidents")
async def list_incidents(
    db: DbSession,
    claims: Claims,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Annotated[IncidentStatus | None, Query(alias="status")] = None,
    service_type: ServiceType | None = None,
    priority: Priority | None = None,
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


@router.get("/incidents/nearby")
async def nearby_incidents(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("provider", "coordinator", "admin"))],
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10, gt=0, le=200),
    service_type: ServiceType | None = None,
):
    # Declared BEFORE /incidents/{incident_id}: routes match in order, and
    # otherwise the word "nearby" is read as an incident id.
    #
    # The ::geography casts make ST_DWithin measure in METRES. On plain
    # geometry (SRID 4326) the distance would be in degrees.
    conditions = [
        Incident.deleted_at.is_(None),
        Incident.status.in_([IncidentStatus.created, IncidentStatus.approved,
                             IncidentStatus.accepted, IncidentStatus.in_progress]),
        text(
            "ST_DWithin(location::geography, "
            "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :r)"
        ),
    ]
    params = {"lng": longitude, "lat": latitude, "r": radius_km * 1000}
    if service_type:
        conditions.append(Incident.service_type == service_type)

    stmt = select(Incident).where(*conditions).limit(100)
    rows = list((await db.execute(stmt, params)).scalars().all())
    return {"data": [_to_response(i) for i in rows]}


def _may_view(incident: Incident, claims: dict) -> bool:
    """Staff and providers see every request; a citizen sees only their own."""
    role = claims.get("role")
    if role in ("coordinator", "admin", "provider"):
        return True
    return role == "citizen" and incident.requester_id == uuid.UUID(claims["sub"])


async def _load_viewable(db: AsyncSession, incident_id: uuid.UUID, claims: dict) -> Incident:
    incident = await db.get(Incident, incident_id)
    if incident is None or incident.deleted_at is not None:
        raise AppError(404, "not_found", "Incident not found.")
    if not _may_view(incident, claims):
        raise AppError(403, "forbidden", "You may not view this request.")
    return incident


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: uuid.UUID, db: DbSession, claims: Claims):
    return _to_response(await _load_viewable(db, incident_id, claims))


@router.get("/incidents/{incident_id}/updates")
async def get_updates(incident_id: uuid.UUID, db: DbSession, claims: Claims):
    await _load_viewable(db, incident_id, claims)   # same rule as the incident itself
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
    # FOR UPDATE: two people acting on the same request at once are made to
    # queue, so e.g. two providers cannot both claim it.
    incident = await db.get(Incident, incident_id, with_for_update=True)
    if incident is None or incident.deleted_at is not None:
        raise AppError(404, "not_found", "Incident not found.")

    role = claims.get("role")
    actor_id = uuid.UUID(claims["sub"])

    # 1. Is this KIND of user allowed to do this at all?
    if not role_allowed(action, role):
        raise AppError(403, "forbidden", f"Role '{role}' may not {action}.")

    # 2. Is it legal from the current state?
    current = incident.status if isinstance(incident.status, IncidentStatus) else IncidentStatus(incident.status)
    if not can_transition(action, current):
        raise AppError(409, "invalid_transition",
                       f"Cannot {action} from '{current.value}'.",
                       details={"current_status": current.value})

    # 3. Is it THIS user's request / organization?
    if role == "citizen" and incident.requester_id != actor_id:
        raise AppError(403, "forbidden", "This is not your request.")

    if action == "accept":
        if incident.assigned_organization_id is not None:
            raise AppError(409, "already_accepted", "This request has already been claimed.")
        org_ids = await member_org_ids(db, actor_id)
        if not org_ids:
            raise AppError(403, "forbidden",
                           "Register or join an organization before claiming requests.")
        org_id = payload.get("organization_id") or org_ids[0]
        if org_id not in org_ids:
            raise AppError(403, "forbidden", "You do not belong to that organization.")
        incident.assigned_organization_id = org_id

    if action in ("start", "complete") and not await is_org_member(
        db, actor_id, incident.assigned_organization_id
    ):
        raise AppError(403, "forbidden",
                       "Only the organization that claimed this request may do that.")

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
    # Tell the requester (saved in the same transaction as the change).
    note = incident_status_changed(
        requester_id=incident.requester_id, actor_id=actor_id, incident_id=incident.id,
        new_status=new_status, reason=payload.get("reason"),
    )
    if note:
        db.add(note)
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
