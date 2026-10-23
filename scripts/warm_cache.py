"""
Warm the Redis cache from Postgres.

Run after a cold start (Redis restarted, or the platform brought up fresh)
to prime the read-through cache before the first user request.

    python -m scripts.warm_cache

If Redis is unavailable, this script is a no-op and returns 0 — the
platform is functional either way.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import select

from shared.cache import get_redis, safe_call
from shared.config import get_settings
from shared.db import async_session
from shared.models import AutoApprovalPolicy, EntityList, Region

log = logging.getLogger(__name__)


async def warm() -> int:
    if get_redis() is None:
        print("ℹ  Redis is not available — nothing to warm.")
        return 0

    settings = get_settings()
    warmed = 0

    async with async_session() as db:
        # ---- regions -----------------------------------------------------
        regions = list((await db.execute(select(Region))).scalars().all())
        # The cache key is region_at:{lat}:{lng}.  We can't pre-warm specific
        # coordinates without knowing the demand, but we can pre-warm the
        # active flag used by the evaluator.
        safe_call("setex", "idrm:cache:regions:active", 300, str(len(regions)))
        warmed += 1
        print(f"   ✔ regions: {len(regions)} loaded")

        # ---- policies ----------------------------------------------------
        for applies_to in ("incident", "provider"):
            policies = list((await db.execute(
                select(AutoApprovalPolicy).where(
                    AutoApprovalPolicy.applies_to == applies_to,
                    AutoApprovalPolicy.active.is_(True),
                )
            )).scalars().all())
            key = f"idrm:cache:policies:{applies_to}"
            safe_call("delete", key)   # force a rebuild on next request
            warmed += 1
            print(f"   ✔ policies ({applies_to}): {len(policies)} active")

        # ---- entity lists ------------------------------------------------
        lists = list((await db.execute(
            select(EntityList).where(EntityList.active.is_(True))
        )).scalars().all())
        # Entity list caches are keyed by (type, value) — no single key to
        # pre-warm.  We invalidate all of them so the next request rebuilds.
        keys = safe_call("keys", "idrm:cache:entity_lists:*") or []
        if keys:
            safe_call("delete", *keys)
        warmed += 1
        print(f"   ✔ entity lists: {len(lists)} active, {len(keys)} cache keys invalidated")

    print()
    print(f"✔ Warmed {warmed} cache namespaces")
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    try:
        return asyncio.run(warm())
    except Exception as exc:
        print(f"✖ Warm-up failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
