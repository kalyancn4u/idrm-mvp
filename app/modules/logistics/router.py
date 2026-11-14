"""Inventory router."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import is_org_member, is_staff
from app.core.dependencies import get_current_claims, get_db, require_role
from app.core.exceptions import AppError
from shared.enums import InventoryKind, InventoryTxnType
from shared.models.logistics import InventoryItem, InventoryLocation, InventoryTransaction

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Claims = Annotated[dict, Depends(get_current_claims)]


class ItemCreate(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    kind: InventoryKind
    location_id: uuid.UUID | None = None
    sku: str | None = None
    unit_of_measure: str | None = None
    quantity: int = 0
    serial_number: str | None = None
    barcode: str | None = None


class TxnCreate(BaseModel):
    txn_type: InventoryTxnType
    quantity_delta: int
    from_location_id: uuid.UUID | None = None
    to_location_id: uuid.UUID | None = None
    incident_id: uuid.UUID | None = None
    note: str | None = None


class LocationCreate(BaseModel):
    organization_id: uuid.UUID
    name: str
    kind: str | None = None
    address: str | None = None


@router.post("/inventory/locations", status_code=status.HTTP_201_CREATED)
async def create_location(
    body: LocationCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    loc = InventoryLocation(
        organization_id=body.organization_id, name=body.name,
        kind=body.kind, address=body.address, created_at=datetime.now(UTC),
    )
    db.add(loc)
    await db.flush()
    return {"id": str(loc.id), "name": loc.name}


@router.post("/inventory/items", status_code=status.HTTP_201_CREATED)
async def create_item(
    body: ItemCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    item = InventoryItem(
        organization_id=body.organization_id, name=body.name, kind=body.kind,
        location_id=body.location_id, sku=body.sku,
        unit_of_measure=body.unit_of_measure, quantity=body.quantity,
        serial_number=body.serial_number, barcode=body.barcode,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    db.add(item)
    await db.flush()
    return {"id": str(item.id), "name": item.name}


@router.get("/inventory/items")
async def list_items(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin", "provider"))],
    organization_id: uuid.UUID | None = None,
):
    stmt = select(InventoryItem).where(InventoryItem.is_active.is_(True))
    if organization_id:
        stmt = stmt.where(InventoryItem.organization_id == organization_id)
    rows = list((await db.execute(stmt)).scalars().all())
    return {"data": [
        {"id": str(i.id), "name": i.name,
         "kind": i.kind.value if hasattr(i.kind, "value") else i.kind,
         "quantity": i.quantity, "unit_of_measure": i.unit_of_measure}
        for i in rows
    ]}


@router.post("/inventory/items/{item_id}/transaction", status_code=status.HTTP_201_CREATED)
async def transact(
    item_id: uuid.UUID, body: TxnCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin", "provider"))],
):
    # FOR UPDATE: two stock movements on one item are applied one after the other.
    item = await db.get(InventoryItem, item_id, with_for_update=True)
    if item is None:
        raise AppError(404, "not_found", "Item not found.")
    if not is_staff(claims) and not await is_org_member(
        db, uuid.UUID(claims["sub"]), item.organization_id
    ):
        raise AppError(403, "forbidden", "This item belongs to another organization.")
    item.quantity += body.quantity_delta
    if item.quantity < 0:
        raise AppError(409, "conflict", "Insufficient inventory.")
    db.add(InventoryTransaction(
        item_id=item_id, txn_type=body.txn_type,
        quantity_delta=body.quantity_delta,
        from_location_id=body.from_location_id, to_location_id=body.to_location_id,
        incident_id=body.incident_id, note=body.note,
        actor_id=uuid.UUID(claims["sub"]), occurred_at=datetime.now(UTC),
    ))
    await db.flush()
    return {"item_id": str(item.id), "new_quantity": item.quantity}

