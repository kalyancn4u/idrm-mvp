"""
bcrypt password hashing + RS256 JWT signing with per-role TTL jitter.

The `exp` claim on every token carries the final jittered value;
verification is unchanged. Jitter spreads refresh load — see ADR-0013.
"""

from __future__ import annotations

import hashlib
import os
import random
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import bcrypt
import jwt

from shared.config import get_settings

BCRYPT_ROUNDS = 12

# bcrypt only ever looks at the first 72 bytes of a password. Older bcrypt
# releases cut longer input silently; newer ones raise an error. Cutting it
# here keeps the behaviour the same on every version, and keeps hashes made
# before this change verifiable.
_BCRYPT_MAX_BYTES = 72


def _password_bytes(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


TokenType = Literal["access", "refresh"]


# ---- Passwords ---------------------------------------------------------------
def hash_password(plain: str) -> str:
    """bcrypt hash, cost 12. The result starts with `$2b$12$`."""
    return bcrypt.hashpw(_password_bytes(plain), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False          # not a bcrypt hash


# ---- Key loading -------------------------------------------------------------
@lru_cache(maxsize=8)
def _read_cached(path: str, mtime_ns: int) -> str:
    return Path(path).read_text(encoding="utf-8")


def _read(path: str) -> str:
    """
    A key file's text, kept in memory.

    Every request verifies a token, so re-reading the file each time is
    wasted work. The file's modification time is part of the cache key: if
    the keys are replaced on disk, the next call picks the new ones up
    without a restart.
    """
    return _read_cached(path, os.stat(path).st_mtime_ns)


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
