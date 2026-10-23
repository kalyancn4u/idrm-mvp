"""Overview page."""

from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import login_required

from dashboard.extensions import db
from dashboard.services.kpi import KPIService

main_bp = Blueprint("main", __name__, template_folder="../templates")


@main_bp.route("/")
@login_required
def overview():
    kpi = KPIService(db.session)
    return render_template(
        "main/dashboard.html",
        kpi=kpi.summary(),
        by_status=kpi.incidents_by_status(),
        by_service=kpi.incidents_by_service(),
        personnel=kpi.personnel_by_status(),
        units=kpi.units_by_status(),
        recent=kpi.recent_activity(limit=10),
    )

