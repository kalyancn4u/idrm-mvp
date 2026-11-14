"""Read-only audit trail."""

from __future__ import annotations

from flask import Blueprint, render_template, request
from flask_login import login_required

from dashboard.extensions import db
from dashboard.services.audit import AuditService

audit_bp = Blueprint("audit", __name__, template_folder="../templates")


@audit_bp.route("/")
@login_required
def trail():
    page = max(1, request.args.get("page", 1, type=int))   # non-numbers fall back to 1
    limit = 50
    svc = AuditService(db.session)
    rows, total = svc.list(
        page=page, limit=limit,
        action=request.args.get("action") or None,
        resource_type=request.args.get("resource_type") or None,
    )
    return render_template(
        "audit/trail.html",
        rows=rows, page=page, total=total,
        pages=max(1, (total + limit - 1) // limit),
        action=request.args.get("action", ""),
        resource_type=request.args.get("resource_type", ""),
        actions=svc.distinct_actions(),
        resource_types=svc.distinct_resource_types(),
    )

