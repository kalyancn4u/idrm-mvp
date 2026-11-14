"""Auto-approval policies, decisions, entity lists."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_claims, get_db, require_role
from app.core.exceptions import AppError
from app.core.pagination import clamp_limit, paginate
from shared import cache
from shared.audit import log_async
from shared.enums import (
    AppliesTo,
    DecisionKind,
    EntityType,
    ListEffect,
    ListType,
    Priority,
    ServiceType,
)
from shared.governance.evaluator import _unsupported_conditions
from shared.governance.schema import validate_policy
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
    service_types: list[ServiceType] = []
    priorities_allowed: list[Priority] = []
    # The period the policy is in force. Outside it the engine ignores the
    # policy and requests go back to waiting for a coordinator.
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    conditions: dict = {}
    caps: dict = {}


def _aware(value: datetime | None) -> datetime | None:
    """A time sent without a timezone is taken to be UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


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
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    now = datetime.now(UTC)
    start = _aware(body.effective_from) or now
    end = _aware(body.effective_to)
    if end is not None and end <= max(start, now):
        raise AppError(422, "validation_error",
                       "effective_to must be in the future and after effective_from.")

    # An admin may write any policy. A coordinator may only switch on
    # auto-approval of help requests for named regions and a fixed period —
    # the "this flood, this district, until Friday" case. Anything open-ended
    # or platform-wide stays an admin decision.
    if claims.get("role") == "coordinator":
        problems = []
        if body.applies_to != AppliesTo.incident:
            problems.append("applies_to must be 'incident'")
        if not body.region_scope:
            problems.append("region_scope must name at least one region")
        if end is None:
            problems.append("effective_to (an end time) is required")
        if problems:
            raise AppError(403, "forbidden",
                           "Coordinators may only create region-scoped, time-limited "
                           "incident policies: " + "; ".join(problems) + ".",
                           details={"problems": problems})

    # Reject a malformed policy now, rather than store it and have the engine
    # silently skip it later.
    try:
        conditions, caps = validate_policy(body.conditions, body.caps)
    except ValidationError as exc:
        raise AppError(422, "validation_error", "Policy conditions or caps are malformed.",
                       details={"errors": exc.errors(include_url=False, include_context=False)}) from exc
    unsupported = _unsupported_conditions(conditions)
    if unsupported:
        raise AppError(422, "validation_error",
                       "These conditions are not enforced by the engine yet: "
                       + ", ".join(unsupported),
                       details={"unsupported_conditions": unsupported})

    actor = uuid.UUID(claims["sub"])
    p = AutoApprovalPolicy(
        code=body.code, name=body.name, applies_to=body.applies_to,
        priority=body.priority, region_scope=body.region_scope,
        service_types=body.service_types, priorities_allowed=body.priorities_allowed,
        effective_from=_aware(body.effective_from), effective_to=end,
        conditions=conditions, caps=caps,
        created_by=actor,
    )
    db.add(p)
    await db.flush()
    await log_async(db, actor_id=actor, action="policy.created",
                    resource_type="auto_approval_policy", resource_id=p.id,
                    new_values={"code": p.code, "applies_to": body.applies_to.value,
                                "region_scope": [str(r) for r in body.region_scope],
                                "effective_from": p.effective_from.isoformat() if p.effective_from else None,
                                "effective_to": p.effective_to.isoformat() if p.effective_to else None,
                                "conditions": conditions, "caps": caps})
    await cache.ainvalidate("policies:*")
    return {"id": str(p.id), "code": p.code}


@router.get("/policies")
async def list_policies(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin"))],
    applies_to: AppliesTo | None = None,
):
    stmt = select(AutoApprovalPolicy)
    if applies_to:
        stmt = stmt.where(AutoApprovalPolicy.applies_to == applies_to)
    rows = list((await db.execute(stmt.order_by(AutoApprovalPolicy.priority.asc()))).scalars().all())
    return {"data": [
        {"id": str(p.id), "code": p.code, "name": p.name,
         "applies_to": p.applies_to.value if hasattr(p.applies_to, "value") else p.applies_to,
         "priority": p.priority, "active": p.active,
         "region_scope": [str(r) for r in (p.region_scope or [])],
         "effective_from": p.effective_from.isoformat() if p.effective_from else None,
         "effective_to": p.effective_to.isoformat() if p.effective_to else None,
         "conditions": p.conditions, "caps": p.caps}
        for p in rows
    ]}


@router.get("/decisions")
async def list_decisions(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin"))],
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    subject_type: AppliesTo | None = None,
    decision: DecisionKind | None = None,
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
    await log_async(db, actor_id=uuid.UUID(claims["sub"]), action="entity_list.created",
                    resource_type="entity_list", resource_id=e.id,
                    new_values={"entity_type": body.entity_type.value,
                                "entity_value": body.entity_value,
                                "list_type": body.list_type.value,
                                "effect": body.effect.value})
    await cache.ainvalidate(f"entity_lists:{body.entity_type.value}:*")
    return {"id": str(e.id)}


@router.get("/entity-lists")
async def list_entity_lists(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin"))],
    entity_type: EntityType | None = None,
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

