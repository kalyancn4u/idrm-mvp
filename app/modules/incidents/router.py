"""
Incidents router — create, list, view and move help requests through their
lifecycle.

Two separate questions are answered for every call:

1. **May this caller act?** — `shared/lifecycle.py` (which role may do which
   action, from which state) plus ownership checks in `_do_transition`.
2. **How much may this caller see?** — `shared/privacy.py` (ADR-0015, the
   "reveal ladder"). Every response goes through `_to_response`, which hides
   what the caller may not see:

   | Caller                                     | Sees                                    |
   |--------------------------------------------|-----------------------------------------|
   | coordinator, admin                         | every request, in full                  |
   | citizen                                    | their own requests, in full             |
   | provider, not in a verified organization   | nothing (403)                           |
   | provider in a verified organization        | approved requests coarsely (~1 km,      |
   |                                            | scrubbed summary, no full description); |
   |                                            | their org's requests in full; never     |
   |                                            | `requester_id`                          |

   The guest `tracking_token` is a bearer secret: it appears only in the
   response that creates the request.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from geoalchemy2.elements import WKTElement
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import is_org_member, verified_member_org_ids
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
from shared.config import get_settings
from shared.enums import AppliesTo, IncidentStatus, Priority, ServiceType
from shared.geo import point_lat_lng
from shared.governance import entity_lists, evaluator
from shared.governance.regions import find_region
from shared.lifecycle import can_transition, next_status, role_allowed
from shared.models.identity import User
from shared.models.incident import Incident, IncidentUpdate
from shared.notifications import incident_status_changed
from shared.privacy import View, incident_view, may_see_requester_id, public_summary, snap

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


def _value(v):
    """An enum's string value; plain strings pass through (rows may hold either)."""
    return v.value if hasattr(v, "value") else v


# ---- Who sees how much (ADR-0015; rules in shared/privacy.py) ----------------
class Viewer:
    """The caller, plus the verified organizations they belong to.

    Loaded once per call so that a list of 100 requests costs one
    membership query, not 100.
    """

    def __init__(self, role: str | None, user_id: uuid.UUID | None,
                 verified_org_ids: list[uuid.UUID]):
        self.role = role
        self.user_id = user_id
        self.verified_org_ids = verified_org_ids


async def _viewer(db: AsyncSession, claims: dict | None) -> Viewer:
    """Build the Viewer from the token claims.

    Only providers need their verified organizations: staff see everything
    and citizens see only their own requests, whatever organizations they
    belong to. No claims means an anonymous caller, who sees nothing.
    """
    if not claims:
        return Viewer(None, None, [])
    role = claims.get("role")
    uid = uuid.UUID(claims["sub"])
    orgs = await verified_member_org_ids(db, uid) if role == "provider" else []
    return Viewer(role, uid, orgs)


def _view_of(i: Incident, viewer: Viewer) -> View:
    """NONE, COARSE or FULL — how much of this request this viewer may see.

    The grace window after closure (PRIVACY_ASSIGNEE_GRACE_HOURS) is measured
    from `updated_at`, the last time the row changed. For a closed request
    that is normally the closing transition. It is an approximation until
    PENDING-TASKS G-4 adds a real `closed_at` column: a later edit (none exists
    today) would restart the window.
    """
    return incident_view(
        role=viewer.role, viewer_id=viewer.user_id, status=_value(i.status),
        requester_id=i.requester_id, assigned_organization_id=i.assigned_organization_id,
        verified_org_ids=viewer.verified_org_ids,
        closed_at=i.updated_at, now=datetime.now(UTC),
        grace_hours=get_settings().privacy_assignee_grace_hours,
    )


def _to_response(i: Incident, view: View, role: str | None) -> dict:
    """Shape one request for one viewer.

    `view` must already be decided (COARSE or FULL; callers never pass NONE —
    such requests are filtered out or refused with 403 before this point).

    Every view has the same keys, so clients need no special cases; hidden
    values are null, and `view` / `location_precision` say which shape this is.
    COARSE snaps the location to the configured grid
    (PRIVACY_COARSE_GRID_DEGREES, ~1 km by default; `location_grid_km` says
    how coarse) and hides the description, rating and review. Every view gets
    `summary`: the description with phone numbers, emails and links removed,
    cut to PRIVACY_SUMMARY_MAX_CHARS — what a provider reads before deciding
    to accept (privacy design §8.4).

    `role` decides `requester_id` separately: providers never get it, even in
    FULL, because it links one person's requests.

    The guest tracking token is never included here — only the create
    response adds it (G-1).
    """
    s = get_settings()
    lat, lng = point_lat_lng(i.location)
    full = view >= View.FULL
    grid = s.privacy_coarse_grid_degrees
    if not full and lat is not None and lng is not None:
        lat, lng = snap(lat, grid), snap(lng, grid)
    return {
        "id": str(i.id),
        "view": "full" if full else "coarse",
        "location_precision": "exact" if full else "approx",
        "location_grid_km": None if full else s.coarse_grid_km,
        "service_type": _value(i.service_type),
        "priority": _value(i.priority),
        "status": _value(i.status),
        "summary": public_summary(i.description, s.privacy_summary_max_chars),
        "description": i.description if full else None,
        "latitude": lat,
        "longitude": lng,
        "requester_id": (str(i.requester_id)
                         if full and i.requester_id and may_see_requester_id(role) else None),
        "assigned_organization_id": str(i.assigned_organization_id) if i.assigned_organization_id else None,
        "auto_approved": i.auto_approved,
        "rating": i.rating if full else None,
        "review": i.review if full else None,
        "created_at": i.created_at.isoformat(),
        "updated_at": i.updated_at.isoformat(),
    }


def _shape(i: Incident, viewer: Viewer) -> dict:
    """Decide the view and shape the request in one step (for lists)."""
    return _to_response(i, _view_of(i, viewer), viewer.role)


def _require_trusted_provider(viewer: Viewer) -> None:
    """Refuse a provider who belongs to no verified organization (gap WF3).

    Anyone may register as a provider and is active at once, so a provider
    is trusted with help requests only through a coordinator-verified
    organization. A clear 403 tells them what to do, instead of an empty
    list that looks like "no requests nearby".
    """
    if viewer.role == "provider" and not viewer.verified_org_ids:
        raise AppError(403, "forbidden",
                       "Join an organization that a coordinator has verified "
                       "before you can see help requests.")


async def _add_update(db, incident_id, from_status, to_status, actor_id, note):
    """Append one row to the request's timeline (`incident_updates`)."""
    db.add(IncidentUpdate(
        incident_id=incident_id, from_status=from_status, to_status=to_status,
        actor_id=actor_id, note=note, created_at=datetime.now(UTC),
    ))
    await db.flush()


# ---- Endpoints ---------------------------------------------------------------
@router.post("/incidents", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit("incident_create", limit=20))])
async def create_incident(data: IncidentCreate, db: DbSession, claims: OptClaims):
    """Raise a help request — signed in, or as a guest with no account.

    A guest gets a tracking token in this response, and only here. The
    request starts in `created` and providers cannot see it until a
    coordinator approves it, or an auto-approval policy in force for that
    region approves it here (ADR-0014).
    """
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
    # The creator sees their own request in full. This is the ONLY response
    # that carries the guest tracking token (G-1): it is a bearer secret, so
    # it is shown once, to the guest, and never again to anyone.
    body = _to_response(incident, View.FULL, "citizen")
    body["tracking_token"] = incident.tracking_token
    return body


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
    """List requests, filtered AND shaped for the caller.

    Filtering happens in SQL (so counts and pages are right); shaping happens
    per row (so a provider's approved-but-not-ours rows come back coarse).
    """
    viewer = await _viewer(db, claims)
    _require_trusted_provider(viewer)

    conditions = [Incident.deleted_at.is_(None)]
    if viewer.role == "citizen":
        conditions.append(Incident.requester_id == viewer.user_id)
    if viewer.role == "provider":
        own = Incident.assigned_organization_id.in_(viewer.verified_org_ids)
        # Approved requests (coarse) and their own organization's (full) —
        # never requests still waiting for approval (ADR-0014, ADR-0015).
        conditions.append(or_(Incident.status == IncidentStatus.approved, own))
        if q:
            # Searching descriptions would reveal text the provider may not
            # read, so a provider's search covers only their own org's work.
            conditions.append(own)
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

    return paginate([_shape(i, viewer) for i in rows], total, page, clamp_limit(limit))


@router.get("/incidents/mine")
async def my_incidents(
    db: DbSession,
    claims: Annotated[dict, Depends(require_role("citizen", "admin"))],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """The caller's own requests, newest first."""
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
    # Only the caller's own requests are selected, so they see them in full.
    # (An admin calling this sees their own requests, not other people's.)
    return paginate([_to_response(i, View.FULL, claims.get("role")) for i in rows],
                    total, page, clamp_limit(limit))


@router.get("/incidents/track/{token}")
async def track_guest(token: str, db: DbSession):
    """Let a guest follow their request with the token from its creation.

    Public on purpose: the token itself is the proof of ownership. It is not
    echoed back, so this response is safe to show on screen.
    """
    incident = (await db.execute(
        select(Incident).where(Incident.tracking_token == token)
    )).scalar_one_or_none()
    if incident is None:
        raise AppError(404, "not_found", "No request matches that tracking token.")
    # Holding the token makes the caller the guest who raised it.
    return _to_response(incident, View.FULL, "citizen")


@router.get("/incidents/nearby")
async def nearby_incidents(
    db: DbSession,
    claims: Annotated[dict, Depends(require_role("provider", "coordinator", "admin"))],
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10, gt=0, le=200),
    service_type: ServiceType | None = None,
):
    """Active requests within `radius_km` of a point, at most 100.

    Staff search by the exact location. Providers search by the snapped
    (~1 km) location and see only approved requests and their own
    organization's — see the comment on the distance condition below.
    """
    # Declared BEFORE /incidents/{incident_id}: routes match in order, and
    # otherwise the word "nearby" is read as an incident id.
    #
    # The ::geography casts make ST_DWithin measure in METRES. On plain
    # geometry (SRID 4326) the distance would be in degrees.
    viewer = await _viewer(db, claims)
    _require_trusted_provider(viewer)

    conditions = [
        Incident.deleted_at.is_(None),
        Incident.status.in_([IncidentStatus.created, IncidentStatus.approved,
                             IncidentStatus.accepted, IncidentStatus.in_progress]),
    ]
    if viewer.role == "provider":
        conditions.append(or_(
            Incident.status == IncidentStatus.approved,
            Incident.assigned_organization_id.in_(viewer.verified_org_ids),
        ))
        # Measure distance from the SNAPPED point. Measuring from the exact
        # point would let a provider find it by shrinking the radius around
        # different centres until the request drops out.
        conditions.append(text(
            "ST_DWithin(ST_SnapToGrid(location, :grid)::geography, "
            "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :r)"
        ))
    else:
        conditions.append(text(
            "ST_DWithin(location::geography, "
            "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :r)"
        ))
    params = {"lng": longitude, "lat": latitude, "r": radius_km * 1000,
              "grid": get_settings().privacy_coarse_grid_degrees}
    if service_type:
        conditions.append(Incident.service_type == service_type)

    stmt = select(Incident).where(*conditions).limit(100)
    rows = list((await db.execute(stmt, params)).scalars().all())
    return {"data": [_shape(i, viewer) for i in rows]}


async def _load_viewable(
    db: AsyncSession, incident_id: uuid.UUID, claims: dict, *, need: View = View.COARSE,
) -> tuple[Incident, Viewer, View]:
    """Load one request and refuse callers whose view is below `need`.

    Returns the request, the viewer and their view, so the caller can shape
    the response without deciding the view a second time. A missing or
    soft-deleted request is 404; one the caller may not see is 403.
    """
    incident = await db.get(Incident, incident_id)
    if incident is None or incident.deleted_at is not None:
        raise AppError(404, "not_found", "Incident not found.")
    viewer = await _viewer(db, claims)
    view = _view_of(incident, viewer)
    if view < need:
        raise AppError(403, "forbidden", "You may not view this request.")
    return incident, viewer, view


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: uuid.UUID, db: DbSession, claims: Claims):
    """One request, coarse or full depending on the caller."""
    incident, viewer, view = await _load_viewable(db, incident_id, claims)
    return _to_response(incident, view, viewer.role)


@router.get("/incidents/{incident_id}/updates")
async def get_updates(incident_id: uuid.UUID, db: DbSession, claims: Claims):
    """The request's timeline: every status change, oldest first."""
    # The timeline holds free-text notes, so it needs the FULL view.
    _, viewer, _ = await _load_viewable(db, incident_id, claims, need=View.FULL)
    staff = viewer.role in ("coordinator", "admin")
    rows = list((await db.execute(
        select(IncidentUpdate).where(IncidentUpdate.incident_id == incident_id)
        .order_by(IncidentUpdate.created_at.asc())
    )).scalars().all())
    return {"data": [
        {"id": str(r.id),
         "from_status": r.from_status.value if r.from_status else None,
         "to_status": r.to_status.value,
         # Who acted is internal; only staff need the account ids.
         "actor_id": str(r.actor_id) if staff and r.actor_id else None,
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
        # Only a VERIFIED organization may claim (gap WF3): anyone can sign up
        # as a provider, so a coordinator's verification is the trust check.
        org_ids = await verified_member_org_ids(db, actor_id)
        if not org_ids:
            raise AppError(403, "forbidden",
                           "Join an organization that a coordinator has verified "
                           "before claiming requests.")
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


async def _respond(db: AsyncSession, claims: dict, incident: Incident) -> dict:
    """After a transition, show the actor only what they may now see."""
    return _shape(incident, await _viewer(db, claims))


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
    return await _respond(db, claims, await _do_transition(db, incident_id, "approve", claims, body.model_dump()))


@router.post("/incidents/{incident_id}/reject")
async def reject(incident_id: uuid.UUID, body: Body, db: DbSession, claims: Claims):
    return await _respond(db, claims, await _do_transition(db, incident_id, "reject", claims, body.model_dump()))


@router.post("/incidents/{incident_id}/accept")
async def accept(incident_id: uuid.UUID, body: Body, db: DbSession, claims: Claims):
    return await _respond(db, claims, await _do_transition(db, incident_id, "accept", claims, body.model_dump()))


@router.post("/incidents/{incident_id}/start")
async def start(incident_id: uuid.UUID, db: DbSession, claims: Claims):
    return await _respond(db, claims, await _do_transition(db, incident_id, "start", claims, {}))


@router.post("/incidents/{incident_id}/complete")
async def complete(incident_id: uuid.UUID, body: Body, db: DbSession, claims: Claims):
    return await _respond(db, claims, await _do_transition(db, incident_id, "complete", claims, body.model_dump()))


@router.post("/incidents/{incident_id}/verify")
async def verify(incident_id: uuid.UUID, body: Body, db: DbSession, claims: Claims):
    return await _respond(db, claims, await _do_transition(db, incident_id, "verify", claims, body.model_dump()))


@router.post("/incidents/{incident_id}/cancel")
async def cancel(incident_id: uuid.UUID, body: Body, db: DbSession, claims: Claims):
    return await _respond(db, claims, await _do_transition(db, incident_id, "cancel", claims, body.model_dump()))
