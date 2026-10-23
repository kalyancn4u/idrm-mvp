"""PostGIS region lookup — one indexed query via ST_Covers."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.cache import cached


@cached("region_at:{lat}:{lng}", ttl=300)
async def find_region(db: AsyncSession, lat: float, lng: float) -> dict | None:
    """Return the region covering a point, or None if none does."""
    stmt = text(
        """
        SELECT id, code, name
          FROM regions
         WHERE is_active
           AND ST_Covers(boundary, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
         LIMIT 1
        """
    )
    row = (await db.execute(stmt, {"lat": lat, "lng": lng})).mappings().first()
    return dict(row) if row else None
