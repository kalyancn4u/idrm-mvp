"""
The four-step auto-approval algorithm.

1. Load policies (Redis cache, 60s TTL; Postgres fallback).
2. Filter by region, service type, priority, effective window.
3. Attempt caps (atomic via Redis Lua; Postgres fallback).
4. Record the decision.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.cache import cached
from shared.config import get_settings
from shared.enums import AppliesTo, DecisionKind, DecisionReason
from shared.governance.counters import try_acquire_caps
from shared.governance.regions import find_region
from shared.governance.schema import PolicyCaps, PolicyConditions
from shared.models.governance import AutoApprovalDecision, AutoApprovalPolicy

log = logging.getLogger(__name__)


@cached("policies:{applies_to}", ttl=60)
async def _load_policies(db: AsyncSession, applies_to: str) -> list[dict]:
    now = datetime.now(UTC)
    stmt = (
        select(AutoApprovalPolicy)
        .where(
            AutoApprovalPolicy.applies_to == applies_to,
            AutoApprovalPolicy.active.is_(True),
        )
        .order_by(AutoApprovalPolicy.priority.asc())
    )
    rows = list((await db.execute(stmt)).scalars().all())

    out = []
    for p in rows:
        if p.effective_from and p.effective_from > now:
            continue
        if p.effective_to and p.effective_to < now:
            continue
        out.append({
            "id": str(p.id),
            "code": p.code,
            "priority": p.priority,
            "region_scope": [str(r) for r in (p.region_scope or [])],
            "service_types": [s.value if hasattr(s, "value") else s for s in (p.service_types or [])],
            "priorities_allowed": [pr.value if hasattr(pr, "value") else pr for pr in (p.priorities_allowed or [])],
            "conditions": p.conditions or {},
            "caps": p.caps or {},
        })
    return out


async def decide(
    db: AsyncSession,
    *,
    subject_type: str,
    subject_id,
    facts: dict[str, Any],
) -> AutoApprovalDecision:
    """Evaluate auto-approval for a subject. Always writes a decision row."""
    settings = get_settings()

    if not settings.auto_approval_enabled:
        return await _record(
            db, subject_type, subject_id,
            decision=DecisionKind.skipped,
            reason=DecisionReason.disabled,
        )

    # 1. Region
    lat = facts.get("latitude")
    lng = facts.get("longitude")
    region = await find_region(db, lat, lng) if lat is not None and lng is not None else None
    if region is None and subject_type == AppliesTo.incident.value:
        return await _record(
            db, subject_type, subject_id,
            decision=DecisionKind.deferred,
            reason=DecisionReason.outside_known_region,
        )

    # 2. Load + filter policies
    policies = await _load_policies(db, subject_type)
    for policy in policies:
        if not _matches_scope(policy, facts, region):
            continue

        try:
            PolicyConditions(**policy["conditions"])
            PolicyCaps(**policy["caps"])
        except Exception as exc:
            log.warning("Policy %s has invalid shape: %s", policy["code"], exc)
            continue

        if policy["conditions"].get("always_reject"):
            return await _record(
                db, subject_type, subject_id,
                decision=DecisionKind.rejected,
                reason=DecisionReason.entity_blocked,
                policy_id=policy["id"],
                region_id=region["id"] if region else None,
            )

        unsupported = _unsupported_conditions(policy["conditions"])
        if unsupported:
            # A rule the engine cannot check must never be treated as passed.
            log.warning("Policy %s skipped: conditions not enforced by the engine: %s",
                        policy["code"], ", ".join(unsupported))
            continue

        if not _matches_conditions(policy["conditions"], facts):
            continue

        # 3. Caps
        counters = await try_acquire_caps(
            db,
            policy_id=policy["id"],
            region_id=region["id"] if region else None,
            service_type=facts.get("service_type"),
            requester_id=facts.get("requester_id"),
            provider_id=facts.get("provider_id"),
            caps=_effective_caps(policy),
        )
        if counters is None:
            continue

        # 4. Approved
        return await _record(
            db, subject_type, subject_id,
            decision=DecisionKind.approved,
            reason=DecisionReason.matched_policy,
            policy_id=policy["id"],
            region_id=region["id"] if region else None,
            counters=counters,
        )

    return await _record(
        db, subject_type, subject_id,
        decision=DecisionKind.deferred,
        reason=DecisionReason.no_policy_matched,
        region_id=region["id"] if region else None,
    )


# Conditions the engine actually evaluates. Anything else that is set makes
# the policy ineligible (see `_unsupported_conditions`).
SUPPORTED_CONDITIONS = frozenset({
    "max_estimated_cost_inr",
    "requester_min_trust_score",
    "max_priority",
    "max_per_requester_per_day",   # enforced as a cap, see _effective_caps
    "always_reject",               # handled in decide()
})

_PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _matches_scope(policy: dict, facts: dict, region: dict | None) -> bool:
    if policy["region_scope"]:
        # A region-scoped policy needs a known region that is in its scope.
        if region is None or str(region["id"]) not in policy["region_scope"]:
            return False
    if policy["service_types"] and facts.get("service_type") not in policy["service_types"]:
        return False
    if policy["priorities_allowed"] and facts.get("priority") not in policy["priorities_allowed"]:
        return False
    return True


def _unsupported_conditions(conditions: dict) -> list[str]:
    """Condition names that are set but that this engine does not evaluate."""
    return sorted(
        k for k, v in conditions.items()
        if v is not None and k not in SUPPORTED_CONDITIONS
    )


def _matches_conditions(conditions: dict, facts: dict) -> bool:
    max_cost = conditions.get("max_estimated_cost_inr")
    if max_cost is not None and facts.get("estimated_cost_inr", 0) > max_cost:
        return False
    min_trust = conditions.get("requester_min_trust_score")
    if min_trust is not None and facts.get("requester_trust_score", 0) < min_trust:
        return False
    max_priority = conditions.get("max_priority")
    if max_priority is not None:
        ceiling = _PRIORITY_RANK.get(max_priority)
        actual = _PRIORITY_RANK.get(facts.get("priority"))
        if ceiling is None or actual is None or actual > ceiling:
            return False
    return True


def _effective_caps(policy: dict) -> dict:
    """
    The policy's caps, with the `max_per_requester_per_day` condition folded
    in: it is a per-day count, so it is enforced by the same counters. Where
    both are given, the stricter one wins.
    """
    caps = dict(policy["caps"])
    limit = policy["conditions"].get("max_per_requester_per_day")
    if limit is not None:
        existing = caps.get("per_requester_per_day")
        caps["per_requester_per_day"] = min(limit, existing) if existing else limit
    return caps


def _as_uuid(value):
    """Ids travel as strings through the JSON cache; the columns want UUIDs."""
    if value is None or isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


async def _record(
    db: AsyncSession,
    subject_type: str,
    subject_id,
    *,
    decision: DecisionKind,
    reason: DecisionReason,
    policy_id=None,
    region_id=None,
    counters: dict | None = None,
) -> AutoApprovalDecision:
    row = AutoApprovalDecision(
        subject_type=subject_type,
        subject_id=subject_id,
        policy_id=_as_uuid(policy_id),
        decision=decision,
        reason=reason,
        counters_at_decision=counters or {},
        evaluated_at=datetime.now(UTC),
    )
    if region_id:
        row.region_id = _as_uuid(region_id)
    db.add(row)
    await db.flush()
    return row
