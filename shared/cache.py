"""
Optional Redis cache.

The platform runs without Redis: every call returns None on failure and
the caller falls through to Postgres. The cache is best-effort.
"""

from __future__ import annotations

import functools
import inspect
import json
import logging
import time
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

_client = None
# After a failed connection Redis is left alone until this moment
# (time.monotonic()), then tried again. 0 means "try now".
_retry_at = 0.0
RETRY_AFTER_SECONDS = 30.0


def get_redis():
    """Return a Redis client, or None if not configured / currently unreachable."""
    global _client, _retry_at

    if _client is not None:
        return _client
    if time.monotonic() < _retry_at:
        return None

    url = __import__("shared.config", fromlist=["get_settings"]).get_settings().redis_url
    if not url:
        _retry_at = float("inf")          # not configured: never retry
        return None

    try:
        import redis as _redis

        client = _redis.Redis.from_url(
            url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
        )
        client.ping()
        _client = client
        log.info("Redis cache enabled")
        return _client
    except Exception as exc:
        log.warning("Redis unavailable (%s) — using Postgres; retry in %ss",
                    exc, int(RETRY_AFTER_SECONDS))
        _retry_at = time.monotonic() + RETRY_AFTER_SECONDS
        return None


def safe_call(method: str, *args, **kwargs) -> Any | None:
    """Call a Redis method, returning None on any failure."""
    c = get_redis()
    if c is None:
        return None
    try:
        return getattr(c, method)(*args, **kwargs)
    except Exception as exc:
        log.debug("Redis %s failed: %s", method, exc)
        return None


def reset_availability() -> None:
    """Test helper — clear the cached unavailable flag."""
    global _client, _retry_at
    _client = None
    _retry_at = 0.0


# ---------------------------------------------------------------------------
# Read-through cache decorator
# ---------------------------------------------------------------------------
def cached(key_template: str, ttl: int):
    """
    Decorator factory.

    `key_template` may use `{arg_name}` placeholders drawn from the
    decorated function's arguments. Any cache failure silently falls through
    to the underlying function.
    """

    def deco(fn: Callable):
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            # Work out each argument's NAME, so "{lat}" in the template finds
            # its value whether the caller wrote f(db, 17.4) or f(db, lat=17.4).
            try:
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                key = "idrm:cache:" + key_template.format(**bound.arguments)
            except (TypeError, IndexError, KeyError):
                return await fn(*args, **kwargs)

            raw = safe_call("get", key)
            if raw is not None:
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    safe_call("delete", key)

            result = await fn(*args, **kwargs)

            try:
                payload = json.dumps(result, default=str)
                safe_call("setex", key, ttl, payload)
            except (TypeError, ValueError) as exc:
                log.debug("Cache write skipped for %s: %s", key, exc)

            return result

        return wrapper

    return deco


def invalidate(pattern: str) -> int:
    """Delete keys matching a pattern. Returns the number removed."""
    keys = safe_call("keys", f"idrm:cache:{pattern}")
    if not keys:
        return 0
    return safe_call("delete", *keys) or 0
