"""
Unified audit writer. FastAPI uses `log_async`; Flask uses `log_sync`.

The `audit_logs` table is append-only at the database level: a trigger
blocks UPDATE and DELETE.

Because a row can never be erased, it must never hold personal data
(ADR-0015, privacy design §8.9): record WHAT happened to WHICH record, not
the email, phone or text involved. Both writers pass `old_values` and
`new_values` through `shared.privacy.redact_audit_values`, which masks
personal keys such as `email` or `phone`. That is a safety net — call sites
should not pass personal values in the first place.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from shared.config import get_settings
from shared.logging import client_ip_ctx
from shared.models.audit import AuditLog
from shared.privacy import redact_audit_values

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
        old_values=redact_audit_values(old_values, _extra_keys()),
        new_values=redact_audit_values(new_values, _extra_keys()),
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
        old_values=redact_audit_values(old_values, _extra_keys()),
        new_values=redact_audit_values(new_values, _extra_keys()),
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


def _extra_keys() -> frozenset[str]:
    """Operator-added audit keys to mask (AUDIT_REDACT_EXTRA_KEYS)."""
    return get_settings().audit_redact_keys
