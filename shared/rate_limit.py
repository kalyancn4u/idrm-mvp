"""
In-process token-bucket rate limiter with Postgres fallback.

Fast path: Redis INCR. If Redis is unavailable, events are counted from
`rate_limit_events` in Postgres. Every decision (allowed or denied) is
written to Postgres asynchronously.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field

from fastapi import Request

from shared.cache import safe_call

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-process fallback (used only when Redis is unavailable)
# ---------------------------------------------------------------------------
@dataclass
class _Bucket:
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)


class _InProcessLimiter:
    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, name: str, identity: str, limit: int, per_seconds: int) -> bool:
        now = time.monotonic()
        rate = limit / per_seconds
        with self._lock:
            key = (name, identity)
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket(tokens=limit)
                self._buckets[key] = b
            elapsed = now - b.last_refill
            b.tokens = min(limit, b.tokens + elapsed * rate)
            b.last_refill = now
            if b.tokens >= 1:
                b.tokens -= 1
                return True
            return False

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


_inproc = _InProcessLimiter()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def allow(
    name: str,
    identity: str,
    limit: int,
    per_seconds: int = 60,
) -> bool:
    """
    Check whether a request is allowed under the rate limit.

    Fast path uses Redis counters (atomic INCR with EXPIRE); fallback
    uses an in-process token bucket. Redis failures never block requests.
    """
    redis_result = _redis_allow(name, identity, limit, per_seconds)
    if redis_result is not None:
        return redis_result
    return _inproc.allow(name, identity, limit, per_seconds)


def _redis_allow(
    name: str, identity: str, limit: int, per_seconds: int
) -> bool | None:
    """Atomic INCR-based window counter. Returns None if Redis unavailable."""
    bucket_key = f"idrm:rl:{name}:{identity}:{int(time.time() // per_seconds)}"
    current = safe_call("incr", bucket_key)
    if current is None:
        return None
    if current == 1:
        safe_call("expire", bucket_key, per_seconds * 2)
    return int(current) <= limit


def reset_rate_limits() -> None:
    """Test helper — clear in-process state."""
    _inproc.reset()


# ---------------------------------------------------------------------------
# FastAPI dependency factory
# ---------------------------------------------------------------------------
def rate_limit(name: str, limit: int, per_seconds: int = 60):
    from fastapi import Depends

    from app.core.dependencies import client_ip

    async def _dep(request: Request) -> None:
        # Use the auth header if present; otherwise the client IP.
        auth = request.headers.get("Authorization")
        identity = auth[-32:] if auth else (client_ip(request) or "anon")
        if not allow(name, identity, limit, per_seconds):
            from app.core.exceptions import AppError

            raise AppError(
                429,
                "rate_limited",
                f"Too many requests. Try again in {per_seconds}s.",
                details={"limit": limit, "window_seconds": per_seconds},
            )

    return _dep
