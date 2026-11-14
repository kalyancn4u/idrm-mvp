"""Policy shape validation and the evaluator's matching logic."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.governance.evaluator import _matches_conditions, _matches_scope
from shared.governance.schema import PolicyCaps, PolicyConditions


def test_conditions_schema_accepts_empty():
    c = PolicyConditions()
    assert c.max_estimated_cost_inr is None


def test_conditions_schema_accepts_full():
    c = PolicyConditions(
        max_estimated_cost_inr=500,
        max_per_requester_per_day=3,
        time_of_day_start="06:00",
    )
    assert c.max_estimated_cost_inr == 500


def test_conditions_schema_rejects_bad_time():
    with pytest.raises(ValidationError):
        PolicyConditions(time_of_day_start="not-a-time")


def test_conditions_extra_fields_allowed():
    """Per ADR-0008, Pydantic does not reject extra fields."""
    c = PolicyConditions(custom_new_field=42)
    assert c.model_dump()["custom_new_field"] == 42


def test_caps_schema_loose():
    k = PolicyCaps(global_per_day=5000, per_region_per_day=500)
    assert k.global_per_day == 5000


def test_matches_scope_region():
    policy = {"region_scope": ["r1", "r2"], "service_types": [], "priorities_allowed": []}
    assert _matches_scope(policy, {"service_type": "food"}, {"id": "r1"})
    assert not _matches_scope(policy, {"service_type": "food"}, {"id": "r3"})


def test_matches_scope_service():
    policy = {"region_scope": [], "service_types": ["food"], "priorities_allowed": []}
    assert _matches_scope(policy, {"service_type": "food"}, None)
    assert not _matches_scope(policy, {"service_type": "medical"}, None)


def test_matches_conditions_cost():
    conditions = {"max_estimated_cost_inr": 500}
    assert _matches_conditions(conditions, {"estimated_cost_inr": 400})
    assert not _matches_conditions(conditions, {"estimated_cost_inr": 600})


def test_matches_conditions_no_cost_no_problem():
    """A policy without max_cost does not reject on cost."""
    assert _matches_conditions({}, {"estimated_cost_inr": 99999})
