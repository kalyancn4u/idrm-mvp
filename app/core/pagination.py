"""Pagination envelope + limit clamp."""

from __future__ import annotations

import math
from typing import Any


def paginate(items: list[Any], total: int, page: int, limit: int) -> dict:
    """Build the ``{data, pagination}`` envelope from an already-sliced list."""
    return {
        "data": items,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": max(1, math.ceil(total / limit)) if limit else 1,
        },
    }


def clamp_limit(limit: int, maximum: int = 100) -> int:
    return max(1, min(limit, maximum))

