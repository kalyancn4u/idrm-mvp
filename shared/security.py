"""
bcrypt password hashing + RS256 JWT signing with per-role TTL jitter.

The `exp` claim on every token carries the final jittered value;
verification is unchanged. Jitter spreads refresh load — see ADR-0013.
"""

from __future__ import annotations

import hashlib
import random
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import jwt
from passlib.context import CryptContext

from shared.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

TokenType = Literal["access", "refresh"]


# ---- Passwords ---------------------------------------------------------------
def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd.verify(plain, hashed)
    except ValueError:
        return False


# ---- Key loading -------------------------------------------------------------
def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


# ---- Jitter ------------------------------------------------------------------
def _jittered_seconds(base_seconds: int, jitter_seconds: int) -> int:
    """Random duration in [base - jitter, base + jitter]."""
    if jitter_seconds <= 0:
        return base_seconds
    offset = random.randint(-jitter_seconds, jitter_seconds)
    return max(1, base_seconds + offset)


# ---- Access token ------------------------------------------------------------
def create_access_token(
    subject: str,
    role: str,
    session_id: str,
    token_version: int,
) -> tuple[str, int]:
    """Sign a jittered access token. Returns (token, expires_in_seconds)."""
    s = get_settings()
    now = datetime.now(UTC)

    base = s.access_ttl_minutes(role) * 60
    jitter = s.access_jitter_minutes(role) * 60
    delta = _jittered_seconds(base, jitter)

    payload: dict[str, Any] = {
        "sub": subject,
        "sid": session_id,
        "ver": token_version,
        "role": role,
        "jti": str(uuid.uuid4()),
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=delta)).timestamp()),
    }
    token = jwt.encode(payload, _read(s.jwt_private_key_path), algorithm="RS256")
    return token, delta


# ---- Refresh token -----------------------------------------------------------
def create_refresh_token(
    subject: str,
    role: str,
    session_id: str,
    family: str,
) -> tuple[str, datetime]:
    """Sign a jittered refresh token. Returns (token, expires_at)."""
    s = get_settings()
    now = datetime.now(UTC)

    base = s.refresh_ttl_days(role) * 86400
    jitter = s.refresh_jitter_days(role) * 86400
    delta = _jittered_seconds(base, jitter)

    expires_at = now + timedelta(seconds=delta)
    payload: dict[str, Any] = {
        "sub": subject,
        "sid": session_id,
        "fam": family,
        "jti": str(uuid.uuid4()),
        "typ": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, _read(s.jwt_private_key_path), algorithm="RS256")
    return token, expires_at


# ---- Verification ------------------------------------------------------------
def decode_token(token: str, expected_typ: TokenType | None = None) -> dict[str, Any]:
    """Verify a token and return its claims. Raises ``jwt.InvalidTokenError``."""
    s = get_settings()
    claims = jwt.decode(token, _read(s.jwt_public_key_path), algorithms=["RS256"])
    if expected_typ and claims.get("typ") != expected_typ:
        raise jwt.InvalidTokenError(
            f"expected token type '{expected_typ}', got '{claims.get('typ')}'"
        )
    return claims


def hash_refresh_token(token: str) -> str:
    """SHA-256 of the refresh token — stored server-side, never the raw token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
