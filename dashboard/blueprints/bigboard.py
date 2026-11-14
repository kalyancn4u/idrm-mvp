"""BigBoard — widget grid situational awareness."""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from dashboard.extensions import db
from dashboard.security import permission_required
from dashboard.services.bigboard import BigBoardService

bigboard_bp = Blueprint("bigboard", __name__, template_folder="../templates")

DEFAULT_WIDGETS = [
    "active_incidents",
    "personnel_summary",
    "unit_summary",
    "orgs_summary",
    "shift_coverage",
    "available_resources",
]


@bigboard_bp.route("/")
@permission_required("view.bigboard")
def index():
    widgets = request.args.getlist("widget") or DEFAULT_WIDGETS
    data = BigBoardService(db.session).widgets(widgets)
    return render_template(
        "bigboard/index.html",
        widgets=widgets,
        data=data,
        all_widgets=DEFAULT_WIDGETS,
    )


@bigboard_bp.route("/data")
@permission_required("view.bigboard")
def data():
    """Polling endpoint for the auto-refresh."""
    widgets = request.args.getlist("widget") or DEFAULT_WIDGETS
    return jsonify(BigBoardService(db.session).widgets(widgets))

