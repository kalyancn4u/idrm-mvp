"""
Pydantic schemas for policy conditions and caps.

Per ADR-0008, these validate **shape only** — no `le`, `ge`, or `max_length`.
The database and the runtime evaluator enforce business limits.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PolicyConditions(BaseModel):
    """Loose shape for `auto_approval_policies.conditions`."""

    model_config = ConfigDict(extra="allow")

    max_priority: str | None = None
    max_estimated_cost_inr: int | None = None
    requester_min_trust_score: int | None = None
    max_per_requester_per_day: int | None = None
    min_region_verified_providers: int | None = None
    time_of_day_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    time_of_day_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    always_reject: bool | None = None

    # Provider-specific
    max_org_type_risk: str | None = None
    requires_documents: list[str] | None = None
    min_service_radius_km: float | None = None
    max_service_radius_km: float | None = None


class PolicyCaps(BaseModel):
    """Loose shape for `auto_approval_policies.caps`."""

    model_config = ConfigDict(extra="allow")

    global_per_day: int | None = None
    per_region_per_day: int | None = None
    per_provider_per_day: int | None = None
    per_service_type_per_day: int | None = None
    per_requester_per_day: int | None = None


def validate_policy(conditions: dict | None, caps: dict | None) -> tuple[dict, dict]:
    """Return validated dicts, raising ValidationError on malformed input."""
    c = PolicyConditions(**(conditions or {})).model_dump(exclude_none=True)
    k = PolicyCaps(**(caps or {})).model_dump(exclude_none=True)
    return c, k
