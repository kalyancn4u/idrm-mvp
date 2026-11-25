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
* After the request closes, the assigned organization keeps the full view for
  a grace window (default 72 h, ADR-0015 D7), then drops to the coarse view.
* The guest tracking token is never part of a normal view; the API adds it
  only to the response that creates the request.

The numbers (grid size, grace hours) are settings — see
docs/design/DATA-CONFIGURATION.md. The functions take them as arguments, so
this module stays free of configuration and easy to test.

Not yet here (later Part G tasks): break-glass for admins (D5), the contact
table and phone reveal, and the ~5 km grid for rural regions (D3) — regions
have no rural marker yet.

Pure functions only: no database, no FastAPI, no Flask (CLAUDE.md rule 1),
so the rules can be unit-tested as a table (tests/unit/test_privacy.py).

Used by: app/modules/incidents/router.py. The staff console does not call it
yet — only coordinators and admins can sign in there, and they see every
request in full under these rules too.

Also here: `redact_audit_values`, which keeps personal values out of the
append-only audit log (Part G task G-6; used by shared/audit.py).
"""

from __future__ import annotations

import enum
import math
import uuid
from collections.abc import Collection
from datetime import datetime, timedelta

# Defaults; the running app passes the configured values from shared/config.py.
# 0.01 degree is about 1.1 km north-south (and about 1 km east-west in India).
COARSE_GRID_DEGREES = 0.01
ASSIGNEE_GRACE_HOURS = 72

# A request in one of these states is over; the grace window starts.
CLOSED_STATUSES = frozenset({"completed", "verified", "cancelled", "rejected"})


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
    closed_at: datetime | None = None,
    now: datetime | None = None,
    grace_hours: int = ASSIGNEE_GRACE_HOURS,
) -> View:
    """Decide the view one viewer gets of one request.

    `status` is the request's status value (e.g. "approved").
    `verified_org_ids` are the VERIFIED organizations the viewer belongs to.
    `closed_at` is when the request entered a closed state; with `now` and
    `grace_hours` it decides whether the assigned organization still gets the
    full view. If either time is missing, the grace window is not applied
    (the safe failure for a rescue in progress is to keep showing it).
    """
    if role in STAFF_ROLES:
        return View.FULL
    if role == "citizen":
        return View.FULL if viewer_id is not None and requester_id == viewer_id else View.NONE
    if role == "provider":
        if not verified_org_ids:
            return View.NONE
        if assigned_organization_id is not None and assigned_organization_id in verified_org_ids:
            if (status in CLOSED_STATUSES and closed_at is not None and now is not None
                    and now - closed_at > timedelta(hours=grace_hours)):
                return View.COARSE          # job over, grace window passed (D7)
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

    The SQL in the nearby search snaps with PostGIS `ST_SnapToGrid` on the
    same grid. The two may differ for a point lying exactly halfway between
    grid lines; that changes which neighbouring point is shown, never the
    precision.
    """
    return round(math.floor(value / step + 0.5) * step, 6)


# ---- Audit: record the fact, not the data (G-6, privacy design §8.9) ---------
#
# `audit_logs` can never be changed or deleted (ADR-0003). Anything personal
# written there could therefore never be erased, which breaks the right to
# erasure. So audit rows say WHAT happened to WHICH record; the personal
# values themselves stay in their own tables, where retention can delete them.
#
# Matching is by key name, case-insensitive, at any depth. Deliberately NOT
# listed: `name` — audit rows record organization, unit and policy names, which
# are not personal data. No call site logs a person's name; if one ever needs
# to, log the user id instead.
REDACTED = "[redacted]"

PERSONAL_AUDIT_KEYS = frozenset({
    "email",
    "phone",
    "guest_contact",
    "description",
    "location",
    "latitude",
    "longitude",
    "address",
    "review",
    "password",
    "token",
    "tracking_token",
    "refresh_token",
    "entity_value",
})

# Any key starting with one of these is personal too (e.g. contact_phone,
# contact_name in the planned incident_contacts table).
PERSONAL_AUDIT_PREFIXES = ("contact_",)


def _is_personal_key(key: object, extra_keys: Collection[str] = ()) -> bool:
    k = str(key).lower()
    return (k in PERSONAL_AUDIT_KEYS or k in extra_keys
            or k.startswith(PERSONAL_AUDIT_PREFIXES))


def redact_audit_values(values, extra_keys: Collection[str] = ()):
    """Return a copy of audit `old_values` / `new_values` with personal values masked.

    The key is kept and its value becomes "[redacted]", so the row still shows
    WHICH field was involved. Nested dicts and lists are handled; None stays
    None. The input is never modified.

    `extra_keys` (lower-case) ADDS keys to the built-in list — the operator's
    AUDIT_REDACT_EXTRA_KEYS setting. There is deliberately no way to remove one.

    This is a safety net. Call sites should not pass personal values at all.
    """
    if values is None:
        return None
    if isinstance(values, dict):
        return {k: (REDACTED if _is_personal_key(k, extra_keys) and v is not None
                    else redact_audit_values(v, extra_keys))
                for k, v in values.items()}
    if isinstance(values, list | tuple):
        return [redact_audit_values(v, extra_keys) for v in values]
    return values
