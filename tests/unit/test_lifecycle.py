"""The incident state machine — pure, no DB."""

from __future__ import annotations

import pytest

from app.modules.incidents.lifecycle import (
    ACTION_ROLES,
    TRANSITIONS,
    can_transition,
    next_status,
    role_allowed,
)
from shared.enums import IncidentStatus as S


def test_all_eight_states_exist():
    assert len(S) == 8


@pytest.mark.parametrize("action,from_state,expected_to", [
    ("approve",  S.created,     S.approved),
    ("accept",   S.approved,    S.accepted),
    ("start",    S.accepted,    S.in_progress),
    ("complete", S.in_progress, S.completed),
    ("verify",   S.completed,   S.verified),
    ("cancel",   S.created,     S.cancelled),
    ("cancel",   S.in_progress, S.cancelled),
    ("reject",   S.created,     S.rejected),
])
def test_legal_transitions(action, from_state, expected_to):
    assert can_transition(action, from_state)
    assert next_status(action) == expected_to


@pytest.mark.parametrize("action,from_state", [
    ("accept",   S.created),      # approval comes first
    ("start",    S.created),
    ("verify",   S.created),
    ("complete", S.accepted),
    ("approve",  S.accepted),
])
def test_illegal_transitions(action, from_state):
    assert not can_transition(action, from_state)


def test_roles_enforced():
    assert role_allowed("accept", "provider")
    assert not role_allowed("accept", "citizen")
    assert role_allowed("verify", "citizen")
    assert not role_allowed("verify", "provider")
    assert role_allowed("approve", "coordinator")


def test_every_action_has_role_and_transition():
    assert set(TRANSITIONS) == set(ACTION_ROLES)

