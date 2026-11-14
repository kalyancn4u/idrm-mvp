"""Inventory overview."""

from __future__ import annotations

from flask import Blueprint, render_template

from dashboard.extensions import db
from dashboard.security import permission_required
from dashboard.services.logistics import LogisticsService

logistics_bp = Blueprint("logistics", __name__, template_folder="../templates")


@logistics_bp.route("/")
@permission_required("view.logistics")
def inventory():
    svc = LogisticsService(db.session)
    return render_template(
        "logistics/inventory.html",
        items=svc.items(),
        locations=svc.locations(),
        low_stock=svc.low_stock(threshold=10),
        expiring=svc.expiring_soon(days=30),
        recent=svc.recent_transactions(limit=20),
    )

