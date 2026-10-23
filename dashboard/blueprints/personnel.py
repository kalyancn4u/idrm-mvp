"""Personnel + unit status overview."""

from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import login_required

from dashboard.extensions import db
from dashboard.services.personnel import PersonnelService

personnel_bp = Blueprint("personnel", __name__, template_folder="../templates")


@personnel_bp.route("/")
@login_required
def status_overview():
    svc = PersonnelService(db.session)
    return render_template(
        "personnel/status.html",
        personnel=svc.all_with_status(),
        units=svc.all_units(),
        recent=svc.recent_status_events(limit=20),
    )

