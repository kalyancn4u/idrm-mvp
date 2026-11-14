"""Kept for backwards compatibility — the state machine now lives in `shared.lifecycle`."""

from shared.lifecycle import (  # noqa: F401
    ACTION_ROLES,
    TERMINAL,
    TRANSITIONS,
    can_transition,
    next_status,
    role_allowed,
)
