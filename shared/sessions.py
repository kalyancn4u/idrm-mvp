"""
Server-side session lifecycle — the field check the JWT design depends on.

Every authenticated request goes through `validate_claims()`. Sessions are
created at login, rotated on refresh, and revoked on logout, password change,
forced-global-logout, and admin action.
"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from shared.config import get_settings
from shared.models.identity import User, UserSession
from shared.security import hash_refresh_token

log = logging.getLogger(__name__)

SESSION_CACHE_PREFIX = "idrm:sess:"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class SecurityError(Exception):
    """Raised by `validate_claims`; converted to a 401 by the caller."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
async def create_session(
    db: AsyncSession,
    *,
    user: User,
    refresh_token: str,
    expires_at: datetime,
    ip: str | None,
    user_agent: str | None,
    device_fingerprint: str | None = None,
) -> UserSession:
    """Create a session, enforcing the per-role concurrent-session limit."""
    await _enforce_session_limit(db, user)

    session = UserSession(
        session_id=secrets.token_urlsafe(24),
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        refresh_token_family=uuid.uuid4(),
        token_version_at_issue=user.token_version,
        expires_at=expires_at,
        ip_address=ip,
        user_agent=user_agent,
        device_fingerprint=device_fingerprint,
    )
    db.add(session)
    await db.flush()
    _cache_session(session)
    return session


async def _enforce_session_limit(db: AsyncSession, user: User) -> None:
    """Evict the oldest session if the user is at the limit."""
    role = user.role.value if hasattr(user.role, "value") else user.role
    limit = get_settings().session_limit(role)

    stmt = (
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .order_by(UserSession.created_at.asc())
    )
    rows = list((await db.execute(stmt)).scalars().all())

    while len(rows) >= limit:
        oldest = rows.pop(0)
        oldest.revoked_at = datetime.now(UTC)
        _invalidate_cache(oldest.session_id)


# ---------------------------------------------------------------------------
# Validate (the field check)
# ---------------------------------------------------------------------------
async def validate_claims(db: AsyncSession, claims: dict) -> tuple[UserSession, User]:
    """
    The session + token-version check on every authenticated request.

    Raises `SecurityError` with a reason code on failure.
    """
    sid = claims.get("sid")
    sub = claims.get("sub")
    ver = claims.get("ver")

    if not sid or not sub or ver is None:
        raise SecurityError("malformed_token")

    # Cache-first lookup for the session
    cached = _cached_session(sid)
    user: User | None = None

    if cached is not None:
        # Session is cached; fetch the user from DB (single indexed lookup)
        try:
            user = await db.get(User, uuid.UUID(sub))
        except (TypeError, ValueError) as exc:
            raise SecurityError("malformed_token") from exc
        if user is None:
            raise SecurityError("user_not_found")
        # Reconstruct a lightweight session object from cache
        session = UserSession(
            id=cached["id"],
            session_id=cached["session_id"],
            user_id=cached["user_id"],
            refresh_token_hash="",
            refresh_token_family=uuid.uuid4(),
            token_version_at_issue=0,
            expires_at=cached["expires_at"],
            last_activity_at=datetime.now(UTC),
            revoked_at=cached["revoked_at"],
        )
    else:
        stmt = (
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .where(UserSession.session_id == sid)
        )
        row = (await db.execute(stmt)).first()
        if row is None:
            raise SecurityError("session_not_found")
        session, user = row
        _cache_session(session)

    # ---- validity chain --------------------------------------------------
    if session.revoked_at is not None:
        raise SecurityError("session_revoked")
    if session.expires_at <= datetime.now(UTC):
        raise SecurityError("session_expired")

    role = user.role.value if hasattr(user.role, "value") else user.role
    idle_hours = get_settings().session_idle_hours(role)
    last_activity = session.last_activity_at or session.expires_at
    if datetime.now(UTC) - last_activity > timedelta(hours=idle_hours):
        raise SecurityError("session_idle_expired")

    if user.status != "active":
        raise SecurityError("account_disabled")

    # ---- the field check -------------------------------------------------
    if int(ver) != int(user.token_version):
        raise SecurityError("token_version_mismatch")

    # Touch activity. Committed by the caller's session context.
    session.last_activity_at = datetime.now(UTC)

    return session, user


# ---------------------------------------------------------------------------
# Revocation
# ---------------------------------------------------------------------------
async def revoke_session(
    db: AsyncSession, session_id: str, *, by: uuid.UUID | None = None
) -> None:
    await db.execute(
        update(UserSession)
        .where(UserSession.session_id == session_id)
        .values(revoked_at=datetime.now(UTC), revoked_by=by)
    )
    _invalidate_cache(session_id)


async def revoke_family(db: AsyncSession, family: uuid.UUID) -> int:
    """Revoke every session in a refresh-token family (used for reuse detection)."""
    result = await db.execute(
        update(UserSession)
        .where(
            UserSession.refresh_token_family == family,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    return result.rowcount or 0


async def revoke_all_for_user(
    db: AsyncSession, user_id: uuid.UUID, *, by: uuid.UUID | None = None
) -> int:
    result = await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC), revoked_by=by)
    )
    return result.rowcount or 0


async def bump_token_version(db: AsyncSession, user: User) -> None:
    """Invalidate every token issued before this moment — the nuclear option."""
    user.token_version = (user.token_version or 1) + 1
    await db.flush()
    from shared.cache import safe_call

    safe_call("setex", f"idrm:userver:{user.id}", 60, str(user.token_version))


# ---------------------------------------------------------------------------
# Cache helpers (best-effort — never raises)
# ---------------------------------------------------------------------------
def _cache_session(session: UserSession) -> None:
    from shared.cache import safe_call

    payload = json.dumps({
        "id": str(session.id),
        "session_id": session.session_id,
        "user_id": str(session.user_id),
        "expires_at": session.expires_at.isoformat(),
        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
    })
    ttl = get_settings().session_cache_ttl_seconds
    safe_call("setex", f"{SESSION_CACHE_PREFIX}{session.session_id}", ttl, payload)


def _cached_session(session_id: str) -> dict | None:
    from shared.cache import safe_call

    raw = safe_call("get", f"{SESSION_CACHE_PREFIX}{session_id}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return {
            "id": uuid.UUID(data["id"]),
            "session_id": data["session_id"],
            "user_id": uuid.UUID(data["user_id"]),
            "expires_at": datetime.fromisoformat(data["expires_at"]),
            "revoked_at": (
                datetime.fromisoformat(data["revoked_at"]) if data["revoked_at"] else None
            ),
        }
    except Exception:
        safe_call("delete", f"{SESSION_CACHE_PREFIX}{session_id}")
        return None


def _invalidate_cache(session_id: str) -> None:
    from shared.cache import safe_call

    safe_call("delete", f"{SESSION_CACHE_PREFIX}{session_id}")
