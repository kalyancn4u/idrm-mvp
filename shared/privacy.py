"""
Who may see how much of a help request (ADR-0015, the "reveal ladder").

This is the first slice of the privacy design
(docs/design/PRIVACY-FIRST-DATA-DESIGN.md §7), covering PENDING-TASKS
Part G tasks G-1 and G-2 and workflow gap WF3:

* A provider sees a request only if they belong to a VERIFIED organization.
  Anyone may sign up as a provider and is active at once, so membership of a
  verified organization is what makes a provider trusted.
* Such a provider sees an APPROVED request only coarsely: type, urgency,
  status, and a location snapped to a ~1 km grid. No description, no
  requester id. (ADR-0014: nothing before approval.)
* Once their organization is assigned, they see the request in full, except
  the requester's account id, which providers never need.
* The guest tracking token is never part of a normal view; the API adds it
  only to the response that creates the request.

Not yet here (later Part G tasks): the 72-hour grace window after closure
(D7), break-glass for admins (D5), the contact table and phone reveal, and
the ~5 km grid for rural regions (D3) — regions have no rural marker yet.

Pure functions only: no database, no FastAPI, no Flask (CLAUDE.md rule 1),
so the rules can be unit-tested as a table.
"""

from __future__ import annotations

import enum
import math
import uuid
from collections.abc import Collection

# 0.01 degree is about 1.1 km north-south (and about 1 km east-west in India).
COARSE_GRID_DEGREES = 0.01


class View(enum.IntEnum):
    """How much of one request a viewer may see. Higher includes lower."""

    NONE = 0
    COARSE = 1
    FULL = 2


STAFF_ROLES = frozenset({"coordinator", "admin"})


def incident_view(
    *,
    role: str | None,
    viewer_id: uuid.UUID | None,
    status: str,
    requester_id: uuid.UUID | None,
    assigned_organization_id: uuid.UUID | None,
    verified_org_ids: Collection[uuid.UUID] = (),
) -> View:
    """Decide the view one viewer gets of one request.

    `status` is the request's status value (e.g. "approved").
    `verified_org_ids` are the VERIFIED organizations the viewer belongs to.
    """
    if role in STAFF_ROLES:
        return View.FULL
    if role == "citizen":
        return View.FULL if viewer_id is not None and requester_id == viewer_id else View.NONE
    if role == "provider":
        if not verified_org_ids:
            return View.NONE
        if assigned_organization_id is not None and assigned_organization_id in verified_org_ids:
            return View.FULL
        if status == "approved":
            return View.COARSE
        return View.NONE
    return View.NONE


def may_see_requester_id(role: str | None) -> bool:
    """Providers never see the requester's account id (it links requests together)."""
    return role in STAFF_ROLES or role == "citizen"


def snap(value: float, step: float = COARSE_GRID_DEGREES) -> float:
    """Round a coordinate to the nearest grid line.

    Deterministic on purpose: random noise could be averaged away by asking
    many times; a snapped value is the same every time.
    """
    return round(math.floor(value / step + 0.5) * step, 6)
