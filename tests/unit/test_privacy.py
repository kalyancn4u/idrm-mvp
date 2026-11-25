"""The reveal ladder and audit redaction (ADR-0015) as tables — pure, no database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from shared.privacy import (
    REDACTED,
    View,
    incident_view,
    may_see_requester_id,
    redact_audit_values,
    snap,
)

ME = uuid.uuid4()
SOMEONE = uuid.uuid4()
MY_ORG = uuid.uuid4()
OTHER_ORG = uuid.uuid4()


def view(role, *, status="approved", requester=SOMEONE, assigned=None, orgs=(MY_ORG,), viewer=ME):
    return incident_view(role=role, viewer_id=viewer, status=status, requester_id=requester,
                         assigned_organization_id=assigned, verified_org_ids=orgs)


@pytest.mark.parametrize("role", ["coordinator", "admin"])
@pytest.mark.parametrize("status", ["created", "approved", "accepted", "verified"])
def test_staff_see_everything(role, status):
    assert view(role, status=status) == View.FULL


def test_citizen_sees_only_their_own():
    assert view("citizen", requester=ME) == View.FULL
    assert view("citizen", requester=SOMEONE) == View.NONE
    assert view("citizen", requester=None) == View.NONE      # a guest's request


@pytest.mark.parametrize("status,assigned,expected", [
    ("created",     None,      View.NONE),     # not approved yet: nothing (ADR-0014)
    ("approved",    None,      View.COARSE),   # open work: coarse card
    ("accepted",    OTHER_ORG, View.NONE),     # another org's job
    ("in_progress", OTHER_ORG, View.NONE),
    ("accepted",    MY_ORG,    View.FULL),     # our job: full
    ("in_progress", MY_ORG,    View.FULL),
    ("completed",   MY_ORG,    View.FULL),
])
def test_provider_in_a_verified_org(status, assigned, expected):
    assert view("provider", status=status, assigned=assigned) == expected


@pytest.mark.parametrize("status,assigned", [
    ("approved", None), ("accepted", MY_ORG), ("created", None),
])
def test_provider_without_a_verified_org_sees_nothing(status, assigned):
    """Anyone may sign up as a provider; only a verified organization is trusted (WF3)."""
    assert view("provider", status=status, assigned=assigned, orgs=()) == View.NONE


@pytest.mark.parametrize("role", [None, "guest", "unknown"])
def test_unknown_callers_see_nothing(role):
    assert view(role) == View.NONE


def test_requester_id_never_shown_to_providers():
    assert may_see_requester_id("provider") is False
    assert may_see_requester_id("coordinator") is True
    assert may_see_requester_id("citizen") is True


@pytest.mark.parametrize("value,expected", [
    (17.3850, 17.39),
    (17.3849, 17.38),
    (78.4867, 78.49),
    (-0.004, -0.0),
    (12.0, 12.0),
])
def test_snap_to_one_hundredth_degree(value, expected):
    assert snap(value) == pytest.approx(expected)


def test_snap_is_deterministic():
    """Same input, same output — so repeated queries cannot be averaged."""
    assert len({snap(17.38512) for _ in range(100)}) == 1


# ---- Audit redaction (G-6): record the fact, not the data -------------------


def test_redaction_masks_personal_keys_and_keeps_the_rest():
    before = {"email": "meera@example.test", "role": "citizen", "phone": "9800000001"}
    assert redact_audit_values(before) == {
        "email": REDACTED, "role": "citizen", "phone": REDACTED,
    }


def test_redaction_never_modifies_its_input():
    before = {"email": "meera@example.test"}
    redact_audit_values(before)
    assert before == {"email": "meera@example.test"}


@pytest.mark.parametrize("key", [
    "email", "EMAIL", "phone", "guest_contact", "description", "location",
    "latitude", "longitude", "address", "review", "password", "token",
    "tracking_token", "refresh_token", "entity_value",
    "contact_phone", "contact_name",
])
def test_every_personal_key_is_masked(key):
    assert redact_audit_values({key: "x"}) == {key: REDACTED}


@pytest.mark.parametrize("key", [
    "status", "role", "reason", "name", "family", "row_count", "entity_type",
    "unit_id", "user_id", "organization_id", "purpose", "size", "title",
])
def test_operational_keys_are_kept(key):
    """Org, unit and policy names, ids and statuses are not personal data."""
    assert redact_audit_values({key: "x"}) == {key: "x"}


def test_nested_values_are_masked():
    before = {"changes": [{"field": "phone", "phone": "98"}], "meta": {"email": "a@b"}}
    assert redact_audit_values(before) == {
        "changes": [{"field": "phone", "phone": REDACTED}], "meta": {"email": REDACTED},
    }


def test_none_and_empty_pass_through():
    assert redact_audit_values(None) is None
    assert redact_audit_values({}) == {}
    assert redact_audit_values({"email": None}) == {"email": None}


# ---- Grace window after closure (ADR-0015 D7) --------------------------------

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("status,hours_since_close,expected", [
    ("in_progress", 500, View.FULL),   # not closed: no clock at all
    ("completed",   1,   View.FULL),   # inside the window
    ("completed",   72,  View.FULL),   # exactly at the edge: still inside
    ("completed",   73,  View.COARSE), # past it: back to the coarse card
    ("verified",    100, View.COARSE),
    ("cancelled",   100, View.COARSE),
])
def test_assignee_grace_window(status, hours_since_close, expected):
    got = incident_view(role="provider", viewer_id=ME, status=status, requester_id=SOMEONE,
                        assigned_organization_id=MY_ORG, verified_org_ids=(MY_ORG,),
                        closed_at=NOW - timedelta(hours=hours_since_close), now=NOW,
                        grace_hours=72)
    assert got == expected


def test_grace_window_is_configurable():
    args = dict(role="provider", viewer_id=ME, status="verified", requester_id=SOMEONE,
                assigned_organization_id=MY_ORG, verified_org_ids=(MY_ORG,),
                closed_at=NOW - timedelta(hours=10), now=NOW)
    assert incident_view(**args, grace_hours=24) == View.FULL
    assert incident_view(**args, grace_hours=0) == View.COARSE


def test_missing_times_keep_the_full_view():
    """Unknown closing time: keep showing it — never hide a job mid-rescue by accident."""
    assert incident_view(role="provider", viewer_id=ME, status="completed", requester_id=SOMEONE,
                         assigned_organization_id=MY_ORG, verified_org_ids=(MY_ORG,)) == View.FULL


def test_staff_and_owner_have_no_grace_window():
    for role, requester in (("coordinator", SOMEONE), ("citizen", ME)):
        assert incident_view(role=role, viewer_id=ME, status="verified", requester_id=requester,
                             assigned_organization_id=MY_ORG, closed_at=NOW - timedelta(days=30),
                             now=NOW) == View.FULL


def test_snap_uses_the_grid_it_is_given():
    assert snap(17.3850, 0.05) == pytest.approx(17.40)
    assert snap(17.3850, 0.1) == pytest.approx(17.4)


def test_operator_can_add_audit_keys_but_not_remove_built_in_ones():
    extra = frozenset({"aadhaar"})
    assert redact_audit_values({"aadhaar": "1234", "email": "a@b"}, extra) == {
        "aadhaar": REDACTED, "email": REDACTED,
    }
    assert redact_audit_values({"aadhaar": "1234"}) == {"aadhaar": "1234"}   # not added: kept
