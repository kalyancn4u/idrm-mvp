"""
Unified audit writer. FastAPI uses `log_async`; Flask uses `log_sync`.

The `audit_logs` table is append-only at the database level: a trigger
blocks UPDATE and DELETE.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from shared.logging import client_ip_ctx
from shared.models.audit import AuditLog

log = logging.getLogger(__name__)


async def log_async(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    row = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address or _ctx_ip(),
    )
    db.add(row)
    try:
        await db.flush()
    except Exception as exc:  # pragma: no cover
        log.error("audit write failed (async): %s", exc)
    return row


def log_sync(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    row = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address or _ctx_ip(),
    )
    db.add(row)
    try:
        db.flush()
    except Exception as exc:  # pragma: no cover
        log.error("audit write failed (sync): %s", exc)
    return row


def _ctx_ip() -> str | None:
    ip = client_ip_ctx.get()
    return None if ip in (None, "-") else ip
