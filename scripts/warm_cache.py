"""
Warm the Redis cache from Postgres.

Run after a cold start (Redis restarted, or the platform brought up fresh)
so the first requests do not all miss the cache at once.

    python -m scripts.warm_cache

What it does:
  - policies      cleared, then loaded once per subject type, which fills the
                  cache (the same loader the engine uses)
  - entity lists  cleared; they are keyed per (type, value), so they refill
                  on first use
  - regions       not warmed: the cache is keyed per coordinate

If Redis is unavailable this is a no-op and exits 0 — the platform works
either way.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import func, select

from shared import cache
from shared.db import async_session
from shared.governance import evaluator
from shared.models import EntityList, Region


async def warm() -> int:
    if cache.get_redis() is None:
        print("ℹ  Redis is not available — nothing to warm.")
        return 0

    async with async_session() as db:
        for applies_to in ("incident", "provider"):
            await cache.ainvalidate(f"policies:{applies_to}")
            policies = await evaluator._load_policies(db, applies_to)   # fills the cache
            print(f"   ✔ policies ({applies_to}): {len(policies)} in force, cached")

        cleared = await cache.ainvalidate("entity_lists:*")
        active = (await db.execute(
            select(func.count()).select_from(EntityList).where(EntityList.active.is_(True))
        )).scalar_one()
        print(f"   ✔ entity lists: {active} active, {cleared} stale cache entries cleared")

        regions = (await db.execute(select(func.count()).select_from(Region))).scalar_one()
        print(f"   ℹ regions: {regions} (cached per coordinate on first lookup)")

    print()
    print("✔ Cache warmed")
    return 0


def main() -> int:
    try:
        return asyncio.run(warm())
    except Exception as exc:
        print(f"✖ Warm-up failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
