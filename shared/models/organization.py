"""Organizations, members, resources, volunteer enrollment, delegations."""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import (
    EnrollmentScope,
    EnrollmentStatus,
    OrgMemberRole,
    OrgType,
    ServiceType,
)
from shared.models.base import Base, SoftDelete, Timestamps, UUIDPrimaryKey

org_type_enum = SAEnum(OrgType, name="org_type")
service_type_enum = SAEnum(ServiceType, name="service_type")
org_member_role_enum = SAEnum(OrgMemberRole, name="org_member_role")
enrollment_scope_enum = SAEnum(EnrollmentScope, name="enrollment_scope")
enrollment_status_enum = SAEnum(EnrollmentStatus, name="enrollment_status")


class Organization(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[OrgType] = mapped_column(org_type_enum, nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    parent_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id")
    )
    service_categories: Mapped[list] = mapped_column(ARRAY(service_type_enum), nullable=False, default=list)
    service_area_center: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326))
    service_radius_km: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=10.0)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_region_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2))
    total_requests_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contact_phone: Mapped[str | None] = mapped_column(String(20))


class OrganizationMember(UUIDPrimaryKey, Base):
    __tablename__ = "organization_members"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[OrgMemberRole] = mapped_column(org_member_role_enum, nullable=False)
    added_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Resource(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "resources"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str | None] = mapped_column(String(50))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    location: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326))
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class VolunteerEnrollment(UUIDPrimaryKey, Base):
    __tablename__ = "volunteer_enrollments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scope_type: Mapped[EnrollmentScope] = mapped_column(enrollment_scope_enum, nullable=False)
    scope_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    status: Mapped[EnrollmentStatus] = mapped_column(
        enrollment_status_enum, nullable=False, default=EnrollmentStatus.pending
    )
    self_enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)


class UserDelegation(UUIDPrimaryKey, Base):
    __tablename__ = "user_delegations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scope_type: Mapped[EnrollmentScope] = mapped_column(enrollment_scope_enum, nullable=False)
    scope_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    can_approve_volunteers: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_approve_incidents: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
