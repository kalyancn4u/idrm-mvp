"""Auto-approval policies, decisions, entity lists."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_claims, get_db, require_role
from app.core.exceptions import AppError
from app.core.pagination import clamp_limit, paginate
from shared.db import async_session
from shared.enums import AppliesTo, EntityType, ListEffect, ListType
from shared.models.governance import AutoApprovalDecision, AutoApprovalPolicy, EntityList

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Claims = Annotated[dict, Depends(get_current_claims)]


class PolicyCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=255)
    applies_to: AppliesTo
    priority: int = 100
    region_scope: list[uuid.UUID] = []
    service_types: list[str] = []
    priorities_allowed: list[str] = []
    conditions: dict = {}
    caps: dict = {}


class EntityListCreate(BaseModel):
    entity_type: EntityType
    entity_value: str
    list_type: ListType
    effect: ListEffect
    scope: dict = {}
    reason: str | None = None


@router.post("/policies", status_code=status.HTTP_201_CREATED)
async def create_policy(
    body: PolicyCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("admin"))],
):
    p = AutoApprovalPolicy(
        code=body.code, name=body.name, applies_to=body.applies_to,
        priority=body.priority, region_scope=body.region_scope,
        service_types=body.service_types, priorities_allowed=body.priorities_allowed,
        conditions=body.conditions, caps=body.caps,
        created_by=uuid.UUID(claims["sub"]),
    )
    db.add(p)
    await db.flush()
    return {"id": str(p.id), "code": p.code}


@router.get("/policies")
async def list_policies(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin"))],
    applies_to: str | None = None,
):
    stmt = select(AutoApprovalPolicy)
    if applies_to:
        stmt = stmt.where(AutoApprovalPolicy.applies_to == applies_to)
    rows = list((await db.execute(stmt.order_by(AutoApprovalPolicy.priority.asc()))).scalars().all())
    return {"data": [
        {"id": str(p.id), "code": p.code, "name": p.name,
         "applies_to": p.applies_to.value if hasattr(p.applies_to, "value") else p.applies_to,
         "priority": p.priority, "active": p.active,
         "conditions": p.conditions, "caps": p.caps}
        for p in rows
    ]}


@router.get("/decisions")
async def list_decisions(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin"))],
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    subject_type: str | None = None,
    decision: str | None = None,
):
    conditions = []
    if subject_type:
        conditions.append(AutoApprovalDecision.subject_type == subject_type)
    if decision:
        conditions.append(AutoApprovalDecision.decision == decision)

    stmt = select(AutoApprovalDecision)
    if conditions:
        stmt = stmt.where(*conditions)

    total = (await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar_one()
    rows = list((await db.execute(
        stmt.order_by(AutoApprovalDecision.evaluated_at.desc())
        .offset((page - 1) * clamp_limit(limit))
        .limit(clamp_limit(limit))
    )).scalars().all())

    return paginate(
        [{"id": str(d.id), "subject_type": d.subject_type.value,
          "subject_id": str(d.subject_id),
          "policy_id": str(d.policy_id) if d.policy_id else None,
          "decision": d.decision.value, "reason": d.reason.value,
          "evaluated_at": d.evaluated_at.isoformat(),
          "counters": d.counters_at_decision}
         for d in rows],
        total, page, clamp_limit(limit),
    )


@router.post("/entity-lists", status_code=status.HTTP_201_CREATED)
async def create_list_entry(
    body: EntityListCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("admin", "coordinator"))],
):
    from datetime import UTC, datetime

    e = EntityList(
        entity_type=body.entity_type, entity_value=body.entity_value,
        list_type=body.list_type, effect=body.effect, scope=body.scope,
        reason=body.reason, active=True,
        effective_from=datetime.now(UTC),
        created_by=uuid.UUID(claims["sub"]),
    )
    db.add(e)
    await db.flush()
    return {"id": str(e.id)}


@router.get("/entity-lists")
async def list_entity_lists(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin"))],
    entity_type: str | None = None,
):
    stmt = select(EntityList).where(EntityList.active.is_(True))
    if entity_type:
        stmt = stmt.where(EntityList.entity_type == entity_type)
    rows = list((await db.execute(stmt.order_by(EntityList.created_at.desc()))).scalars().all())
    return {"data": [
        {"id": str(e.id),
         "entity_type": e.entity_type.value if hasattr(e.entity_type, "value") else e.entity_type,
         "entity_value": e.entity_value,
         "list_type": e.list_type.value, "effect": e.effect.value,
         "reason": e.reason, "active": e.active}
        for e in rows
    ]}

