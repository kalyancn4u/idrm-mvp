"""
Shared FastAPI dependencies — including the JWT + session field check.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from shared.config import get_settings
from shared.db import async_session
from shared.rate_limit import allow_async
from shared.security import decode_token
from shared.sessions import SecurityError, validate_claims

_bearer = HTTPBearer(auto_error=False)

_REASON_MAP: dict[str, tuple[int, str, str]] = {
    "malformed_token":        (401, "malformed_token", "Token is malformed."),
    "session_not_found":      (401, "session_not_found", "Session not found."),
    "session_revoked":        (401, "session_revoked", "Session has been revoked."),
    "session_expired":        (401, "session_expired", "Session has expired."),
    "session_idle_expired":   (401, "session_idle_expired", "Session idle timeout."),
    "user_not_found":         (401, "user_not_found", "User no longer exists."),
    "account_disabled":       (401, "account_disabled", "Account is not active."),
    "token_version_mismatch": (401, "token_version_mismatch", "Token is stale."),
}


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_claims(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if creds is None or not creds.credentials:
        raise AppError(401, "unauthorized", "Missing bearer token.")
    try:
        claims = decode_token(creds.credentials, expected_typ="access")
    except jwt.ExpiredSignatureError as exc:
        raise AppError(401, "token_expired", "Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise AppError(401, "invalid_token", "Access token is invalid.") from exc

    try:
        session, user = await validate_claims(db, claims)
    except SecurityError as exc:
        status, code, msg = _REASON_MAP.get(exc.reason, (401, exc.reason, "Token rejected."))
        raise AppError(status, code, msg) from exc

    claims["_session"] = session
    claims["_user"] = user
    return claims


async def get_optional_claims(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict | None:
    if creds is None or not creds.credentials:
        return None
    try:
        return await get_current_claims(creds, db)
    except AppError:
        return None


def require_role(*roles: str):
    async def _guard(claims: Annotated[dict, Depends(get_current_claims)]) -> dict:
        if claims.get("role") not in roles:
            raise AppError(403, "forbidden", "Insufficient role.",
                           details={"required_roles": list(roles)})
        return claims

    return _guard


def client_ip(request: Request) -> str:
    """
    The caller's address.

    `X-Forwarded-For` is written by whoever sends the request, so it is only
    believed when TRUST_FORWARDED_FOR says a proxy we control sets it.
    """
    if get_settings().trust_forwarded_for:
        fwd = request.headers.get("X-Forwarded-For")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "-"


def rate_limit(name: str, limit: int, per_seconds: int = 60):
    """Dependency: at most `limit` calls per window, counted per client address."""

    async def _dep(request: Request) -> None:
        if not await allow_async(name, client_ip(request), limit, per_seconds):
            raise AppError(
                429,
                "rate_limited",
                f"Too many requests. Try again in {per_seconds}s.",
                details={"limit": limit, "window_seconds": per_seconds},
            )

    return _dep
