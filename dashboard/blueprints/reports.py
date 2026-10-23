"""Rollup reports + CSV export."""

from __future__ import annotations

import csv
import io

from flask import Blueprint, Response, render_template, request
from flask_login import current_user, login_required

from dashboard.extensions import db
from dashboard.services.incidents import IncidentService
from dashboard.services.reports import ReportService

reports_bp = Blueprint("reports", __name__, template_folder="../templates")


@reports_bp.route("/")
@login_required
def index():
    days = int(request.args.get("days", 30))
    svc = ReportService(db.session)
    return render_template(
        "reports/index.html",
        days=days,
        daily=svc.daily_created(days),
        response_times=svc.response_times(days),
        top_orgs=svc.top_organizations(10),
    )


@reports_bp.route("/export/incidents.csv")
@login_required
def export_incidents():
    from shared.audit import log_sync

    rows, _ = IncidentService(db.session).list(page=1, limit=100_000)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "service_type", "priority", "status", "created_at"])
    for r in rows:
        w.writerow([
            str(r.id),
            r.service_type.value if hasattr(r.service_type, "value") else r.service_type,
            r.priority.value if hasattr(r.priority, "value") else r.priority,
            r.status.value if hasattr(r.status, "value") else r.status,
            r.created_at.isoformat() if r.created_at else "",
        ])

    log_sync(db.session, actor_id=current_user.id,
             action="dashboard.export.incidents_csv",
             resource_type="export", new_values={"row_count": len(rows)})
    db.session.commit()

    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="incidents.csv"'})

