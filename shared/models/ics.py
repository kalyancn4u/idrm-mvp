"""ICS command structure, lanes, run logs."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import IcsLaneType, IcsRole, RunLogType
from shared.models.base import Base, UUIDPrimaryKey

ics_role_enum = SAEnum(IcsRole, name="ics_role")
ics_lane_enum = SAEnum(IcsLaneType, name="ics_lane_type")
run_log_enum = SAEnum(RunLogType, name="run_log_type")


class IncidentCommand(UUIDPrimaryKey, Base):
    __tablename__ = "incident_commands"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    commander_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    ics_role: Mapped[IcsRole] = mapped_column(
        ics_role_enum, nullable=False, default=IcsRole.incident_commander
    )
    objectives: Mapped[str | None] = mapped_column(Text)
    safety_message: Mapped[str | None] = mapped_column(Text)
    established_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    demobilized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class IncidentLane(UUIDPrimaryKey, Base):
    __tablename__ = "incident_lanes"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    parent_lane_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("incident_lanes.id", ondelete="CASCADE")
    )
    lane_type: Mapped[IcsLaneType] = mapped_column(ics_lane_enum, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str | None] = mapped_column(String(32))
    lead_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    objectives: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LaneAssignment(UUIDPrimaryKey, Base):
    __tablename__ = "lane_assignments"

    lane_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("incident_lanes.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE")
    )
    role: Mapped[str | None] = mapped_column(String(64))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunLog(UUIDPrimaryKey, Base):
    __tablename__ = "run_logs"

    log_type: Mapped[RunLogType] = mapped_column(run_log_enum, nullable=False)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL")
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RunLogEntry(UUIDPrimaryKey, Base):
    __tablename__ = "run_log_entries"

    run_log_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("run_logs.id", ondelete="CASCADE"), nullable=False
    )
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL")
    )
    hours: Mapped[float | None] = mapped_column(Numeric(6, 2))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
