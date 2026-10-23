"""Audit log router — read-only."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.core.pagination import clamp_limit, paginate
from shared.db import async_session
from shared.models.audit import AuditLog

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("")
async def list_audit(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin"))],
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
):
    conditions = []
    if actor_id:
        conditions.append(AuditLog.actor_id == actor_id)
    if action:
        conditions.append(AuditLog.action.ilike(f"%{action}%"))
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if resource_id:
        conditions.append(AuditLog.resource_id == resource_id)

    stmt = select(AuditLog)
    if conditions:
        stmt = stmt.where(*conditions)

    total = (await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar_one()
    rows = list((await db.execute(
        stmt.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * clamp_limit(limit))
        .limit(clamp_limit(limit))
    )).scalars().all())

    return paginate(
        [{"id": str(r.id),
          "actor_id": str(r.actor_id) if r.actor_id else None,
          "action": r.action, "resource_type": r.resource_type,
          "resource_id": str(r.resource_id) if r.resource_id else None,
          "ip_address": r.ip_address, "old_values": r.old_values,
          "new_values": r.new_values, "created_at": r.created_at.isoformat()}
         for r in rows],
        total, page, clamp_limit(limit),
    )

