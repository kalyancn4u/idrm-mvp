"""
Ownership checks shared by the routers.

A *role* says what kind of user someone is. It does not say WHICH
organization's data they may touch. These helpers answer the second question.

For help requests, membership is not enough: a provider must belong to an
organization a coordinator has VERIFIED (`verified_member_org_ids`), because
anyone may register as a provider (ADR-0015, gap WF3). How much of a request
each caller sees is decided in `shared/privacy.py`, not here.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.organization import Organization, OrganizationMember
from shared.models.personnel import Unit, UnitMember

STAFF_ROLES = frozenset({"coordinator", "admin"})


def is_staff(claims: dict) -> bool:
    """Coordinators and admins act across organizations."""
    return claims.get("role") in STAFF_ROLES


async def member_org_ids(db: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Organizations the user belongs to, verified or not, oldest membership first.

    Not used for help requests any more — use `verified_member_org_ids`
    there. Kept for checks where any membership is enough.
    """
    stmt = (
        select(OrganizationMember.organization_id)
        .where(OrganizationMember.user_id == user_id)
        .order_by(OrganizationMember.added_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def verified_member_org_ids(db: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Organizations the user belongs to that a coordinator has VERIFIED.

    Anyone may register as a provider, so membership alone does not make
    someone trusted with help requests; a verified organization does
    (ADR-0015, gap WF3).
    """
    stmt = (
        select(OrganizationMember.organization_id)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .where(
            OrganizationMember.user_id == user_id,
            Organization.is_verified.is_(True),
            Organization.deleted_at.is_(None),
        )
        .order_by(OrganizationMember.added_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def is_org_member(
    db: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID | None
) -> bool:
    if organization_id is None:
        return False
    stmt = select(OrganizationMember.id).where(
        OrganizationMember.user_id == user_id,
        OrganizationMember.organization_id == organization_id,
    ).limit(1)
    return (await db.execute(stmt)).first() is not None


async def is_unit_member(
    db: AsyncSession, user_id: uuid.UUID, unit_id: uuid.UUID | None
) -> bool:
    """True if the user is on the unit's crew, or belongs to the unit's organization."""
    if unit_id is None:
        return False
    crew = select(UnitMember.id).where(
        UnitMember.unit_id == unit_id,
        UnitMember.user_id == user_id,
        UnitMember.left_at.is_(None),
    ).limit(1)
    if (await db.execute(crew)).first() is not None:
        return True
    unit = await db.get(Unit, unit_id)
    return unit is not None and await is_org_member(db, user_id, unit.organization_id)
