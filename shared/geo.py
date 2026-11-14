"""
Tiny geometry helpers — just enough to read a POINT back out of PostGIS.

`geoalchemy2.shape.to_shape` would do this, but it needs the `shapely`
package, which is not a dependency of this project. A point is simple enough
to decode by hand.
"""

from __future__ import annotations

import re
import struct

_WKT_POINT = re.compile(r"POINT\s*\(\s*(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s*\)", re.IGNORECASE)
_HAS_SRID = 0x20000000
_POINT = 1


def point_lat_lng(value) -> tuple[float | None, float | None]:
    """
    Return `(latitude, longitude)` for a PostGIS POINT, or `(None, None)`.

    Accepts what SQLAlchemy/GeoAlchemy2 hands back:
      - a WKBElement (a row loaded from the database) — binary, hex-encoded
      - a WKTElement (a row just created in this request) — text "POINT(lng lat)"
    PostGIS stores X = longitude, Y = latitude; this returns them the other
    way round because the API speaks latitude first.
    """
    if value is None:
        return None, None
    try:
        data = getattr(value, "data", value)
        if isinstance(data, str):
            m = _WKT_POINT.search(data)
            if m:
                return float(m.group(2)), float(m.group(1))
            raw = bytes.fromhex(data)              # hex-encoded WKB
        else:
            raw = bytes(data)                      # bytes / memoryview

        order = "<" if raw[0] == 1 else ">"
        (geom_type,) = struct.unpack_from(order + "I", raw, 1)
        offset = 5
        if geom_type & _HAS_SRID:
            offset += 4
        if geom_type & 0xFF != _POINT:
            return None, None
        lng, lat = struct.unpack_from(order + "dd", raw, offset)
        return lat, lng
    except (ValueError, IndexError, struct.error, TypeError):
        return None, None
