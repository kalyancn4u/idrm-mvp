"""Policies, decisions, entity lists — read views + writes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from shared import cache
from shared.audit import log_sync
from shared.models.governance import (
    AutoApprovalDecision,
    AutoApprovalPolicy,
    EntityList,
)


class PolicyService:
    def __init__(self, session):
        self.db = session

    def list_policies(self):
        return list(self.db.execute(
            select(AutoApprovalPolicy).order_by(AutoApprovalPolicy.priority.asc())
        ).scalars().all())

    def get_policy(self, policy_id: uuid.UUID) -> AutoApprovalPolicy | None:
        return self.db.get(AutoApprovalPolicy, policy_id)

    def set_active(self, policy_id: uuid.UUID, active: bool, actor_id: uuid.UUID) -> None:
        p = self.get_policy(policy_id)
        if p is None:
            return
        p.active = active
        self.db.flush()
        cache.invalidate("policies:*")     # the engine must see the change now
        log_sync(self.db, actor_id=actor_id, action="policy.toggled",
                 resource_type="auto_approval_policy", resource_id=policy_id,
                 new_values={"active": active})

    def list_decisions(self, *, page: int, limit: int,
                       decision: str | None = None):
        conditions = []
        if decision:
            conditions.append(AutoApprovalDecision.decision == decision)
        stmt = select(AutoApprovalDecision)
        if conditions:
            stmt = stmt.where(*conditions)
        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()
        rows = list(self.db.execute(
            stmt.order_by(AutoApprovalDecision.evaluated_at.desc())
            .offset((page - 1) * limit).limit(limit)
        ).scalars().all())
        return rows, total

    def override_decision(self, decision_id: uuid.UUID, actor_id: uuid.UUID, reason: str):
        d = self.db.get(AutoApprovalDecision, decision_id)
        if d is None:
            return
        d.overridden_at = datetime.now(UTC)
        d.overridden_by = actor_id
        d.override_reason = reason
        self.db.flush()
        log_sync(self.db, actor_id=actor_id, action="decision.overridden",
                 resource_type="auto_approval_decision", resource_id=decision_id,
                 new_values={"reason": reason})

    def list_entity_lists(self, *, entity_type: str | None = None):
        stmt = select(EntityList)
        if entity_type:
            stmt = stmt.where(EntityList.entity_type == entity_type)
        return list(self.db.execute(
            stmt.order_by(EntityList.created_at.desc())
        ).scalars().all())

    def create_entity_list(self, *, entity_type: str, entity_value: str,
                           list_type: str, effect: str, reason: str,
                           actor_id: uuid.UUID):
        e = EntityList(
            entity_type=entity_type, entity_value=entity_value,
            list_type=list_type, effect=effect, reason=reason,
            active=True, effective_from=datetime.now(UTC),
            created_by=actor_id,
        )
        self.db.add(e)
        self.db.flush()
        cache.invalidate(f"entity_lists:{entity_type}:*")
        log_sync(self.db, actor_id=actor_id, action="entity_list.created",
                 resource_type="entity_list", resource_id=e.id,
                 # The blocked value (an email, phone or IP) stays in
                 # `entity_lists`, not in the permanent audit log (ADR-0015).
                 new_values={"entity_type": entity_type,
                             "list_type": list_type, "effect": effect})
        return e

    def deactivate_entity_list(self, entry_id: uuid.UUID, actor_id: uuid.UUID):
        e = self.db.get(EntityList, entry_id)
        if e:
            e.active = False
            self.db.flush()
            log_sync(self.db, actor_id=actor_id, action="entity_list.deactivated",
                     resource_type="entity_list", resource_id=entry_id)

