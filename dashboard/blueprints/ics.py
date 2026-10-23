"""ICS command board."""

from __future__ import annotations

import uuid

from flask import Blueprint, abort, render_template
from flask_login import login_required

from dashboard.extensions import db
from dashboard.services.ics import ICSService
from dashboard.services.incidents import IncidentService

ics_bp = Blueprint("ics", __name__, template_folder="../templates")


@ics_bp.route("/<uuid:incident_id>")
@login_required
def command_board(incident_id: uuid.UUID):
    incident = IncidentService(db.session).get(incident_id)
    if incident is None:
        abort(404)
    svc = ICSService(db.session)
    lanes = svc.lanes(incident_id)
    return render_template(
        "ics/command_board.html",
        incident=incident,
        commands=svc.active_command(incident_id),
        lanes=[(l, svc.lane_assignments(l.id)) for l in lanes],
        run_logs=svc.run_logs_for(incident_id),
    )

