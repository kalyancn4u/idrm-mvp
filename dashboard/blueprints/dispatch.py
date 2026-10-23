"""Dispatch console — the three-panel CAD workflow."""

from __future__ import annotations

import uuid

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required

from dashboard.extensions import db
from dashboard.security import permission_required
from dashboard.services.dispatch import DispatchService
from dashboard.services.incidents import IncidentService

dispatch_bp = Blueprint("dispatch", __name__, template_folder="../templates")


@dispatch_bp.route("/")
@login_required
def console():
    svc = DispatchService(db.session)
    return render_template(
        "dispatch/console.html",
        incidents=svc.open_incidents(limit=50),
        personnel=svc.available_personnel(limit=50),
        units=svc.available_units(limit=50),
        selected_id=request.args.get("selected"),
    )


@dispatch_bp.route("/assign", methods=["POST"])
@permission_required("act.incidents")
def assign():
    incident_id = uuid.UUID(request.form["incident_id"])
    unit_id = request.form.get("unit_id")
    user_id = request.form.get("user_id")
    if not unit_id and not user_id:
        flash("Select a unit or a person to assign.", "error")
        return redirect(url_for("dispatch.console"))

    DispatchService(db.session).assign(
        incident_id=incident_id,
        actor_id=current_user.id,
        unit_id=uuid.UUID(unit_id) if unit_id else None,
        user_id=uuid.UUID(user_id) if user_id else None,
        note=(request.form.get("note") or "").strip() or None,
    )
    db.session.commit()
    flash("Dispatched.", "success")
    return redirect(url_for("dispatch.console", selected=str(incident_id)))


@dispatch_bp.route("/offer", methods=["POST"])
@permission_required("act.incidents")
def offer():
    incident_id = uuid.UUID(request.form["incident_id"])
    unit_id = request.form.get("unit_id")
    user_id = request.form.get("user_id")
    if not unit_id and not user_id:
        flash("Select a unit or a person to offer to.", "error")
        return redirect(url_for("dispatch.console"))

    DispatchService(db.session).offer(
        incident_id=incident_id,
        actor_id=current_user.id,
        unit_id=uuid.UUID(unit_id) if unit_id else None,
        user_id=uuid.UUID(user_id) if user_id else None,
    )
    db.session.commit()
    flash("Offer sent.", "success")
    return redirect(url_for("dispatch.console", selected=str(incident_id)))


@dispatch_bp.route("/release/<uuid:assignment_id>", methods=["POST"])
@permission_required("act.incidents")
def release(assignment_id: uuid.UUID):
    DispatchService(db.session).release(assignment_id, current_user.id)
    db.session.commit()
    flash("Assignment released.", "success")
    return redirect(url_for("dispatch.console"))

