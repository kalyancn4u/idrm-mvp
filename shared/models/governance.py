"""Governance models — regions, policies, decisions, entity lists, BigBoard."""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import (
    AppliesTo,
    DecisionKind,
    DecisionReason,
    EntityType,
    IdentityType,
    ListEffect,
    ListType,
    Priority,
    ServiceType,
)
from shared.models.base import Base, Timestamps, UUIDPrimaryKey

applies_to_enum = SAEnum(AppliesTo, name="applies_to")
decision_kind_enum = SAEnum(DecisionKind, name="decision_kind")
decision_reason_enum = SAEnum(DecisionReason, name="decision_reason")
list_type_enum = SAEnum(ListType, name="list_type")
list_effect_enum = SAEnum(ListEffect, name="list_effect")
entity_type_enum = SAEnum(EntityType, name="entity_type")
identity_type_enum = SAEnum(IdentityType, name="identity_type")
service_type_enum = SAEnum(ServiceType, name="service_type")
priority_enum = SAEnum(Priority, name="priority")


class Region(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "regions"

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    boundary: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=False)
    parent_region_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("regions.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AutoApprovalPolicy(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "auto_approval_policies"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    applies_to: Mapped[AppliesTo] = mapped_column(applies_to_enum, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parent_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("auto_approval_policies.id")
    )
    region_scope: Mapped[list] = mapped_column(ARRAY(PgUUID(as_uuid=True)), nullable=False, default=list)
    service_types: Mapped[list] = mapped_column(ARRAY(service_type_enum), nullable=False, default=list)
    priorities_allowed: Mapped[list] = mapped_column(ARRAY(priority_enum), nullable=False, default=list)
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    caps: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))


class AutoApprovalDecision(UUIDPrimaryKey, Base):
    __tablename__ = "auto_approval_decisions"

    subject_type: Mapped[AppliesTo] = mapped_column(applies_to_enum, nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("auto_approval_policies.id")
    )
    decision: Mapped[DecisionKind] = mapped_column(decision_kind_enum, nullable=False)
    reason: Mapped[DecisionReason] = mapped_column(decision_reason_enum, nullable=False)
    evaluated_conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    counters_at_decision: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    region_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("regions.id"))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    overridden_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    override_reason: Mapped[str | None] = mapped_column(Text)


class EntityList(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "entity_lists"

    entity_type: Mapped[EntityType] = mapped_column(entity_type_enum, nullable=False)
    entity_value: Mapped[str] = mapped_column(Text, nullable=False)
    list_type: Mapped[ListType] = mapped_column(list_type_enum, nullable=False)
    effect: Mapped[ListEffect] = mapped_column(list_effect_enum, nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))


class EntityListMatch(UUIDPrimaryKey, Base):
    __tablename__ = "entity_list_matches"

    list_entry_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("entity_lists.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[EntityType] = mapped_column(entity_type_enum, nullable=False)
    entity_value: Mapped[str] = mapped_column(Text, nullable=False)
    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    effect: Mapped[ListEffect] = mapped_column(list_effect_enum, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RateLimitEvent(UUIDPrimaryKey, Base):
    __tablename__ = "rate_limit_events"

    bucket: Mapped[str] = mapped_column(String(64), nullable=False)
    identity: Mapped[str] = mapped_column(String(255), nullable=False)
    identity_type: Mapped[IdentityType] = mapped_column(identity_type_enum, nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MutualAidAgreement(UUIDPrimaryKey, Base):
    __tablename__ = "mutual_aid_agreements"

    from_org_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    to_org_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    auto_accept: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_personnel: Mapped[int | None] = mapped_column(Integer)
    max_units: Mapped[int | None] = mapped_column(Integer)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))


class BigboardConfig(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "bigboard_configs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Default")
    layout: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BigboardWidget(UUIDPrimaryKey, Base):
    __tablename__ = "bigboard_widgets"

    config_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("bigboard_configs.id", ondelete="CASCADE"), nullable=False
    )
    widget_type: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    span: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    row_span: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
