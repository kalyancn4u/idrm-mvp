"""The reveal ladder (ADR-0015) as a table — pure, no database."""

from __future__ import annotations

import uuid

import pytest

from shared.privacy import View, incident_view, may_see_requester_id, snap

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
