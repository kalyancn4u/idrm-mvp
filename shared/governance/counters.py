"""
Auto-approval cap counters.

Redis is the hot path. When Redis is unavailable, counters fall back to
counting decisions in Postgres within the current window.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.cache import get_redis, safe_call

log = logging.getLogger(__name__)

LUA_ACQUIRE = """
for i = 1, #KEYS do
    local current = tonumber(redis.call('GET', KEYS[i]) or '0')
    local limit = tonumber(ARGV[i])
    if limit > 0 and current >= limit then
        return { err = 'cap_exceeded:' .. i }
    end
end
local results = {}
for i = 1, #KEYS do
    results[i] = redis.call('INCR', KEYS[i])
    redis.call('EXPIRE', KEYS[i], 172800)
end
return results
"""


def _bucket_key(kind: str, value: str, day: str) -> str:
    return f"idrm:cap:{kind}:{value}:{day}"


async def try_acquire_caps(
    db: AsyncSession,
    *,
    policy_id: uuid.UUID,
    region_id: uuid.UUID | None,
    service_type: str | None,
    requester_id: uuid.UUID | None,
    provider_id: uuid.UUID | None,
    caps: dict,
) -> dict | None:
    """Attempt to increment all cap counters atomically.

    Returns the counters dict on success, None if any cap was exceeded.
    Falls back to a Postgres count when Redis is unavailable.
    """
    day = datetime.now(UTC).strftime("%Y-%m-%d")

    dimensions: list[tuple[str, str, int]] = []
    if caps.get("global_per_day"):
        dimensions.append(("global", "all", caps["global_per_day"]))
    if caps.get("per_region_per_day") and region_id:
        dimensions.append(("region", str(region_id), caps["per_region_per_day"]))
    if caps.get("per_provider_per_day") and provider_id:
        dimensions.append(("provider", str(provider_id), caps["per_provider_per_day"]))
    if caps.get("per_service_type_per_day") and service_type:
        dimensions.append(("service", service_type, caps["per_service_type_per_day"]))
    if caps.get("per_requester_per_day") and requester_id:
        dimensions.append(("req", str(requester_id), caps["per_requester_per_day"]))

    if not dimensions:
        return {}

    keys = [_bucket_key(k, v, day) for k, v, _ in dimensions]
    limits = [limit for _, _, limit in dimensions]

    redis_result = _try_redis_lua(keys, limits)
    if redis_result is not None:
        return dict(zip((f"{k}:{v}" for k, v, _ in dimensions), redis_result, strict=False))

    return await _postgres_fallback(db, policy_id, dimensions)


def _try_redis_lua(keys: list[str], limits: list[int]) -> list[int] | None:
    c = get_redis()
    if c is None:
        return None
    try:
        script = c.register_script(LUA_ACQUIRE)
        result = script(keys=keys, args=limits)
        if isinstance(result, list):
            return [int(x) for x in result]
        return None
    except Exception as exc:
        log.debug("Redis Lua failed: %s", exc)
        return None


async def _postgres_fallback(
    db: AsyncSession, policy_id: uuid.UUID, dimensions: list[tuple[str, str, int]]
) -> dict | None:
    counters: dict[str, int] = {}
    for kind, value, limit in dimensions:
        if kind in ("req", "provider", "service"):
            continue  # not tracked in the fallback path

        where = [
            "policy_id = :policy",
            "decision = 'approved'",
            "evaluated_at >= date_trunc('day', now())",
        ]
        params: dict = {"policy": policy_id}
        if kind == "region":
            where.append("region_id = :r")
            params["r"] = uuid.UUID(value)

        sql = text(f"SELECT count(*) FROM auto_approval_decisions WHERE {' AND '.join(where)}")
        count = (await db.execute(sql, params)).scalar_one()
        if count >= limit:
            return None
        counters[f"{kind}:{value}"] = count + 1

    return counters
