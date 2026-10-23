"""Inventory — locations, items, transactions."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import InventoryKind, InventoryTxnType
from shared.models.base import Base, UUIDPrimaryKey

inventory_kind_enum = SAEnum(InventoryKind, name="inventory_kind")
inventory_txn_enum = SAEnum(InventoryTxnType, name="inventory_txn_type")


class InventoryLocation(UUIDPrimaryKey, Base):
    __tablename__ = "inventory_locations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)
    location: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InventoryItem(UUIDPrimaryKey, Base):
    __tablename__ = "inventory_items"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("inventory_locations.id", ondelete="SET NULL")
    )
    sku: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[InventoryKind] = mapped_column(inventory_kind_enum, nullable=False)
    unit_of_measure: Mapped[str | None] = mapped_column(String(32))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    serial_number: Mapped[str | None] = mapped_column(String(128))
    barcode: Mapped[str | None] = mapped_column(String(128))
    expires_at: Mapped[date | None] = mapped_column(Date)
    condition: Mapped[str | None] = mapped_column(String(32))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InventoryTransaction(UUIDPrimaryKey, Base):
    __tablename__ = "inventory_transactions"

    item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False
    )
    txn_type: Mapped[InventoryTxnType] = mapped_column(inventory_txn_enum, nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    from_location_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("inventory_locations.id", ondelete="SET NULL")
    )
    to_location_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("inventory_locations.id", ondelete="SET NULL")
    )
    from_user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    to_user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    incident_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("incidents.id"))
    note: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
