"""Alerts list + create."""

from __future__ import annotations

import uuid

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from dashboard.extensions import db
from dashboard.security import permission_required
from dashboard.services.alerts import AlertService

alerts_bp = Blueprint("alerts", __name__, template_folder="../templates")


@alerts_bp.route("/")
@login_required
def list_view():
    page = max(1, int(request.args.get("page", 1)))
    limit = 25
    rows, total = AlertService(db.session).list(
        page=page, limit=limit, active_only=request.args.get("all") != "1"
    )
    return render_template(
        "alerts/list.html", rows=rows, page=page, total=total,
        pages=max(1, (total + limit - 1) // limit),
    )


@alerts_bp.route("/new", methods=["GET", "POST"])
@permission_required("act.alerts")
def create():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        message = (request.form.get("message") or "").strip()
        severity = (request.form.get("severity") or "info").strip()
        if len(title) < 3 or len(message) < 10 or severity not in {"info", "warning", "critical"}:
            flash("Supply a title (3+ chars), message (10+ chars) and severity.", "error")
            return render_template("alerts/create.html")

        AlertService(db.session).create(
            title=title, message=message, severity=severity, actor_id=current_user.id,
        )
        db.session.commit()
        flash("Alert issued.", "success")
        return redirect(url_for("alerts.list_view"))
    return render_template("alerts/create.html")


@alerts_bp.route("/<uuid:alert_id>/deactivate", methods=["POST"])
@permission_required("act.alerts")
def deactivate(alert_id: uuid.UUID):
    AlertService(db.session).deactivate(alert_id, current_user.id)
    db.session.commit()
    flash("Alert deactivated.", "success")
    return redirect(url_for("alerts.list_view"))

