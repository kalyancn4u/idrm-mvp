"""Privacy and retention settings: safe defaults, range checks, cross-checks."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.config import Settings


def make(**overrides) -> Settings:
    # _env_file=None: test the class defaults, not whatever .env holds.
    return Settings(_env_file=None, **overrides)


def test_defaults_match_adr_0015():
    s = make()
    assert s.privacy_coarse_grid_degrees == 0.01
    assert s.privacy_rural_grid_degrees == 0.05
    assert s.privacy_assignee_grace_hours == 72
    assert s.retention_contact_days == 30
    assert s.file_link_ttl_seconds == 300
    assert s.privacy_summary_max_chars == 140
    assert s.privacy_k_anonymity == 5
    assert s.coarse_grid_km == 1.1


@pytest.mark.parametrize("field,bad", [
    ("privacy_coarse_grid_degrees", 0.0001),   # ~11 m: effectively exact
    ("privacy_coarse_grid_degrees", 1.0),
    ("privacy_assignee_grace_hours", -1),
    ("file_link_ttl_seconds", 10),
    ("file_link_ttl_seconds", 86400),
    ("privacy_k_anonymity", 1),                # k = 1 publishes individuals
    ("retention_contact_days", 0),
    ("privacy_summary_max_chars", 10),
])
def test_out_of_range_values_refuse_to_load(field, bad):
    with pytest.raises(ValidationError):
        make(**{field: bad})


def test_rural_grid_may_not_be_finer_than_urban():
    with pytest.raises(ValidationError):
        make(privacy_coarse_grid_degrees=0.05, privacy_rural_grid_degrees=0.01)


def test_grace_window_may_not_outlive_the_contact_details():
    with pytest.raises(ValidationError):
        make(privacy_assignee_grace_hours=720, retention_contact_days=7)
    assert make(privacy_assignee_grace_hours=168, retention_contact_days=7)


def test_extra_audit_keys_are_parsed():
    s = make(audit_redact_extra_keys=" Aadhaar, vehicle_no ,,")
    assert s.audit_redact_keys == frozenset({"aadhaar", "vehicle_no"})
    assert make().audit_redact_keys == frozenset()
