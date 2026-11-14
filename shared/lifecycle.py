"""
The incident lifecycle state machine — pure data, no DB, no HTTP.

Lives in `shared/` because BOTH apps change incident status: the API for
every transition, the dashboard for approve / reject. One table of legal
moves means neither app can put an incident into a state the other does not
expect.
"""

from __future__ import annotations

from shared.enums import IncidentStatus as S

TRANSITIONS: dict[str, tuple[frozenset[S], S]] = {
    "approve":  (frozenset({S.created}), S.approved),
    "reject":   (frozenset({S.created, S.approved}), S.rejected),
    # A provider may claim a request only once it is approved — by a
    # coordinator, or by an auto-approval policy a coordinator switched on
    # for that region and period. Without either, it waits in `created`.
    "accept":   (frozenset({S.approved}), S.accepted),
    "assign":   (frozenset({S.created, S.approved}), S.accepted),
    "start":    (frozenset({S.accepted}), S.in_progress),
    "complete": (frozenset({S.in_progress}), S.completed),
    "verify":   (frozenset({S.completed}), S.verified),
    "cancel":   (frozenset({S.created, S.approved, S.accepted, S.in_progress}), S.cancelled),
}

ACTION_ROLES: dict[str, frozenset[str]] = {
    "approve":  frozenset({"coordinator", "admin"}),
    "reject":   frozenset({"coordinator", "admin"}),
    "accept":   frozenset({"provider"}),
    "assign":   frozenset({"coordinator", "admin"}),
    "start":    frozenset({"provider"}),
    "complete": frozenset({"provider"}),
    "verify":   frozenset({"citizen"}),
    "cancel":   frozenset({"citizen", "coordinator", "admin"}),
}

TERMINAL = frozenset({S.verified, S.cancelled, S.rejected})


def can_transition(action: str, current: S) -> bool:
    spec = TRANSITIONS.get(action)
    return spec is not None and current in spec[0]


def next_status(action: str) -> S:
    return TRANSITIONS[action][1]


def role_allowed(action: str, role: str) -> bool:
    return role in ACTION_ROLES.get(action, frozenset())

