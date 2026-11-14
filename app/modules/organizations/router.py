"""Organizations, resources, volunteers router."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_claims, get_db, require_role
from app.core.exceptions import AppError
from app.core.pagination import clamp_limit, paginate
from shared.audit import log_async
from shared.db import async_session
from shared.enums import EnrollmentScope, EnrollmentStatus, OrgType, ServiceType
from shared.models.organization import (
    Organization, OrganizationMember, VolunteerEnrollment,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Claims = Annotated[dict, Depends(get_current_claims)]


class OrgCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    type: OrgType
    service_categories: list[ServiceType]
    latitude: float | None = None
    longitude: float | None = None
    service_radius_km: float = Field(default=10.0, gt=0, le=500)
    capacity: int = 0
    contact_phone: str | None = None


class VolunteerEnrollBody(BaseModel):
    scope_type: EnrollmentScope
    scope_id: uuid.UUID | None = None
    notes: str | None = None


def _org_public(o: Organization) -> dict:
    return {
        "id": str(o.id), "name": o.name,
        "type": o.type.value if hasattr(o.type, "value") else o.type,
        "owner_user_id": str(o.owner_user_id),
        "service_categories": [s.value if hasattr(s, "value") else s for s in (o.service_categories or [])],
        "service_radius_km": float(o.service_radius_km),
        "capacity": o.capacity, "available_capacity": o.available_capacity,
        "is_available": o.is_available, "is_verified": o.is_verified,
        "rating": float(o.rating) if o.rating else None,
        "created_at": o.created_at.isoformat(),
    }


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
async def create_org(
    body: OrgCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("provider", "admin"))],
):
    uid = uuid.UUID(claims["sub"])
    existing = (await db.execute(
        select(Organization).where(Organization.owner_user_id == uid,
                                   Organization.deleted_at.is_(None))
    )).scalar_one_or_none()
    if existing:
        raise AppError(409, "conflict", "You already own an organization.")

    org = Organization(
        name=body.name, type=body.type, owner_user_id=uid,
        service_categories=body.service_categories,
        service_radius_km=body.service_radius_km,
        capacity=body.capacity,
        available_capacity=body.capacity,
        contact_phone=body.contact_phone,
    )
    if body.latitude is not None and body.longitude is not None:
        from geoalchemy2.elements import WKTElement
        org.service_area_center = WKTElement(f"POINT({body.longitude} {body.latitude})", srid=4326)
    db.add(org)
    await db.flush()

    db.add(OrganizationMember(
        organization_id=org.id, user_id=uid, role="owner",
        added_by=uid, added_at=datetime.now(UTC),
    ))
    await db.flush()

    await log_async(db, actor_id=uid, action="organization.created",
                    resource_type="organization", resource_id=org.id,
                    new_values={"name": org.name})
    return _org_public(org)


@router.get("/organizations")
async def list_orgs(
    db: DbSession,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    verified: bool | None = None,
    service_type: ServiceType | None = None,
    q: str | None = None,
):
    conditions = [Organization.deleted_at.is_(None)]
    if verified is not None:
        conditions.append(Organization.is_verified.is_(verified))
    if service_type:
        conditions.append(Organization.service_categories.any(service_type))
    if q:
        conditions.append(Organization.name.ilike(f"%{q}%"))

    total = (await db.execute(
        select(func.count()).select_from(Organization).where(*conditions)
    )).scalar_one()
    rows = list((await db.execute(
        select(Organization).where(*conditions)
        .order_by(Organization.created_at.desc())
        .offset((page - 1) * clamp_limit(limit))
        .limit(clamp_limit(limit))
    )).scalars().all())

    return paginate([_org_public(o) for o in rows], total, page, clamp_limit(limit))


@router.post("/organizations/{org_id}/verify")
async def verify_org(
    org_id: uuid.UUID, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    org = await db.get(Organization, org_id)
    if org is None:
        raise AppError(404, "not_found", "Organization not found.")
    org.is_verified = True
    org.verified_by = uuid.UUID(claims["sub"])
    org.verified_at = datetime.now(UTC)
    await db.flush()
    await log_async(db, actor_id=uuid.UUID(claims["sub"]),
                    action="organization.verified",
                    resource_type="organization", resource_id=org.id)
    return _org_public(org)


# ---- Volunteers ---------------------------------------------------------------
@router.post("/volunteers/enroll", status_code=status.HTTP_201_CREATED)
async def enroll(body: VolunteerEnrollBody, db: DbSession, claims: Claims):
    if claims.get("role") not in ("provider", "coordinator", "admin"):
        raise AppError(403, "forbidden", "Only providers may enroll as volunteers.")
    enrollment = VolunteerEnrollment(
        user_id=uuid.UUID(claims["sub"]),
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        status=EnrollmentStatus.pending,
        self_enrolled_at=datetime.now(UTC),
        notes=body.notes,
    )
    db.add(enrollment)
    await db.flush()
    await log_async(db, actor_id=uuid.UUID(claims["sub"]),
                    action="volunteer.enrolled",
                    resource_type="volunteer_enrollment", resource_id=enrollment.id,
                    new_values={"scope_type": body.scope_type.value,
                                "scope_id": str(body.scope_id) if body.scope_id else None})
    return {"id": str(enrollment.id), "status": enrollment.status.value}


@router.get("/volunteers/mine")
async def my_enrollments(db: DbSession, claims: Claims):
    rows = list((await db.execute(
        select(VolunteerEnrollment).where(
            VolunteerEnrollment.user_id == uuid.UUID(claims["sub"]),
        ).order_by(VolunteerEnrollment.self_enrolled_at.desc())
    )).scalars().all())
    return {"data": [
        {
            "id": str(r.id),
            "scope_type": r.scope_type.value if hasattr(r.scope_type, "value") else r.scope_type,
            "scope_id": str(r.scope_id) if r.scope_id else None,
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "self_enrolled_at": r.self_enrolled_at.isoformat(),
            "approved_at": r.approved_at.isoformat() if r.approved_at else None,
        } for r in rows
    ]}


@router.post("/volunteers/{enrollment_id}/approve")
async def approve_enrollment(
    enrollment_id: uuid.UUID, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    e = await db.get(VolunteerEnrollment, enrollment_id)
    if e is None:
        raise AppError(404, "not_found", "Enrollment not found.")
    e.status = EnrollmentStatus.active
    e.approved_by = uuid.UUID(claims["sub"])
    e.approved_at = datetime.now(UTC)
    await db.flush()
    await log_async(db, actor_id=uuid.UUID(claims["sub"]),
                    action="volunteer.approved",
                    resource_type="volunteer_enrollment", resource_id=e.id)
    return {"id": str(e.id), "status": e.status.value}


@router.post("/volunteers/{enrollment_id}/reject")
async def reject_enrollment(
    enrollment_id: uuid.UUID, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
    reason: str = Query(..., min_length=3),
):
    e = await db.get(VolunteerEnrollment, enrollment_id)
    if e is None:
        raise AppError(404, "not_found", "Enrollment not found.")
    e.status = EnrollmentStatus.rejected
    e.rejection_reason = reason
    await db.flush()
    await log_async(db, actor_id=uuid.UUID(claims["sub"]),
                    action="volunteer.rejected",
                    resource_type="volunteer_enrollment", resource_id=e.id)
    return {"id": str(e.id), "status": e.status.value}

