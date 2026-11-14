"""Incidents list + detail + coordinator actions."""

from __future__ import annotations

import uuid

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from dashboard.extensions import db
from dashboard.security import permission_required
from dashboard.services import enum_or_none
from dashboard.services.incidents import IncidentService
from shared.enums import IncidentStatus, Priority, ServiceType

incidents_bp = Blueprint("incidents", __name__, template_folder="../templates")


@incidents_bp.route("/")
@permission_required("view.incidents")
def list_view():
    page = max(1, request.args.get("page", 1, type=int))   # non-numbers fall back to 1
    limit = 25
    svc = IncidentService(db.session)
    rows, total = svc.list(
        page=page, limit=limit,
        status=enum_or_none(IncidentStatus, request.args.get("status")),
        service_type=enum_or_none(ServiceType, request.args.get("service_type")),
        priority=enum_or_none(Priority, request.args.get("priority")),
        q=(request.args.get("q") or "").strip() or None,
    )
    return render_template(
        "incidents/list.html",
        rows=rows, page=page, total=total,
        pages=max(1, (total + limit - 1) // limit),
        status=request.args.get("status", ""),
        service_type=request.args.get("service_type", ""),
        priority=request.args.get("priority", ""),
        q=request.args.get("q", ""),
    )


@incidents_bp.route("/<uuid:incident_id>")
@permission_required("view.incidents")
def detail(incident_id: uuid.UUID):
    svc = IncidentService(db.session)
    incident = svc.get(incident_id)
    if incident is None:
        abort(404)
    return render_template(
        "incidents/detail.html",
        incident=incident,
        updates=svc.updates_for(incident_id),
    )


@incidents_bp.route("/<uuid:incident_id>/approve", methods=["POST"])
@permission_required("act.incidents")
def approve(incident_id: uuid.UUID):
    try:
        IncidentService(db.session).coordinator_approve(
            incident_id, current_user.id,
            (request.form.get("note") or "").strip() or None,
        )
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("incidents.detail", incident_id=incident_id))
    db.session.commit()
    flash("Incident approved.", "success")
    return redirect(url_for("incidents.detail", incident_id=incident_id))


@incidents_bp.route("/<uuid:incident_id>/reject", methods=["POST"])
@permission_required("act.incidents")
def reject(incident_id: uuid.UUID):
    reason = (request.form.get("reason") or "").strip()
    if len(reason) < 3:
        flash("A reason is required.", "error")
        return redirect(url_for("incidents.detail", incident_id=incident_id))
    try:
        IncidentService(db.session).coordinator_reject(incident_id, current_user.id, reason)
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("incidents.detail", incident_id=incident_id))
    db.session.commit()
    flash("Incident rejected.", "success")
    return redirect(url_for("incidents.detail", incident_id=incident_id))

