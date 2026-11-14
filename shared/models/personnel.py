"""Personnel status and units."""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import PersonnelStatus, UnitStatus
from shared.models.base import Base, SoftDelete, Timestamps, UUIDPrimaryKey

personnel_status_enum = SAEnum(PersonnelStatus, name="personnel_status")
unit_status_enum = SAEnum(UnitStatus, name="unit_status")


class PersonnelStatusRow(UUIDPrimaryKey, Base):
    __tablename__ = "personnel_statuses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[PersonnelStatus] = mapped_column(
        personnel_status_enum, nullable=False, default=PersonnelStatus.off_duty
    )
    staffing_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326))
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PersonnelStatusEvent(UUIDPrimaryKey, Base):
    __tablename__ = "personnel_status_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[PersonnelStatus | None] = mapped_column(personnel_status_enum)
    to_status: Mapped[PersonnelStatus] = mapped_column(personnel_status_enum, nullable=False)
    staffing_level: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL")
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Unit(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "units"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str | None] = mapped_column(String(50))
    callsign: Mapped[str | None] = mapped_column(String(32))
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    home_location: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class UnitMember(UUIDPrimaryKey, Base):
    __tablename__ = "unit_members"

    unit_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")
    is_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UnitStatusRow(UUIDPrimaryKey, Base):
    __tablename__ = "unit_statuses"

    unit_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[UnitStatus] = mapped_column(
        unit_status_enum, nullable=False, default=UnitStatus.in_quarters
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL")
    )
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326))
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UnitStatusEvent(UUIDPrimaryKey, Base):
    __tablename__ = "unit_status_events"

    unit_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[UnitStatus | None] = mapped_column(unit_status_enum)
    to_status: Mapped[UnitStatus] = mapped_column(unit_status_enum, nullable=False)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
