"""Incident — the core "help request" — and its timeline."""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.enums import IncidentStatus, Priority, ServiceType
from shared.models.base import Base, SoftDelete, Timestamps, UUIDPrimaryKey

service_type_enum = SAEnum(ServiceType, name="service_type")
priority_enum = SAEnum(Priority, name="priority")
incident_status_enum = SAEnum(IncidentStatus, name="incident_status")


class Incident(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_incidents_rating_range"),
    )

    service_type: Mapped[ServiceType] = mapped_column(service_type_enum, nullable=False)
    priority: Mapped[Priority] = mapped_column(priority_enum, nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        incident_status_enum, nullable=False, default=IncidentStatus.created
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[object] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    region_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("regions.id"))
    requester_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    guest_contact: Mapped[str | None] = mapped_column(String(20))
    tracking_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    assigned_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id")
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    auto_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_policy_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    review: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    updates = relationship("IncidentUpdate", back_populates="incident", cascade="all, delete-orphan")


class IncidentUpdate(UUIDPrimaryKey, Base):
    __tablename__ = "incident_updates"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[IncidentStatus | None] = mapped_column(incident_status_enum)
    to_status: Mapped[IncidentStatus] = mapped_column(incident_status_enum, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    incident = relationship("Incident", back_populates="updates")
