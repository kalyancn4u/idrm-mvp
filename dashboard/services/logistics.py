"""Inventory read views."""

from __future__ import annotations

from sqlalchemy import select

from shared.models.logistics import InventoryItem, InventoryLocation, InventoryTransaction


class LogisticsService:
    def __init__(self, session):
        self.db = session

    def items(self, organization_id=None):
        stmt = select(InventoryItem).where(InventoryItem.is_active.is_(True))
        if organization_id:
            stmt = stmt.where(InventoryItem.organization_id == organization_id)
        return list(self.db.execute(stmt.order_by(InventoryItem.name.asc())).scalars().all())

    def locations(self, organization_id=None):
        stmt = select(InventoryLocation).where(InventoryLocation.is_active.is_(True))
        if organization_id:
            stmt = stmt.where(InventoryLocation.organization_id == organization_id)
        return list(self.db.execute(stmt.order_by(InventoryLocation.name.asc())).scalars().all())

    def recent_transactions(self, limit: int = 50):
        return list(self.db.execute(
            select(InventoryTransaction)
            .order_by(InventoryTransaction.occurred_at.desc()).limit(limit)
        ).scalars().all())

    def low_stock(self, threshold: int = 10):
        return list(self.db.execute(
            select(InventoryItem).where(
                InventoryItem.is_active.is_(True),
                InventoryItem.quantity <= threshold,
            ).order_by(InventoryItem.quantity.asc())
        ).scalars().all())

    def expiring_soon(self, days: int = 30):
        from datetime import date, timedelta
        cutoff = date.today() + timedelta(days=days)
        return list(self.db.execute(
            select(InventoryItem).where(
                InventoryItem.is_active.is_(True),
                InventoryItem.expires_at.is_not(None),
                InventoryItem.expires_at <= cutoff,
            ).order_by(InventoryItem.expires_at.asc())
        ).scalars().all())

