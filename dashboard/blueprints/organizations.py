"""Organizations list + verify + volunteer approval."""

from __future__ import annotations

import uuid

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from dashboard.extensions import db
from dashboard.security import permission_required
from dashboard.services.organizations import OrganizationService

orgs_bp = Blueprint("organizations", __name__, template_folder="../templates")


@orgs_bp.route("/")
@login_required
def list_view():
    page = max(1, request.args.get("page", 1, type=int))   # non-numbers fall back to 1
    limit = 25
    verified_param = request.args.get("verified")
    verified = None if verified_param in (None, "") else verified_param == "1"

    rows, total = OrganizationService(db.session).list(
        page=page, limit=limit, verified=verified,
        q=(request.args.get("q") or "").strip() or None,
    )
    return render_template(
        "organizations/list.html",
        rows=rows, page=page, total=total,
        pages=max(1, (total + limit - 1) // limit),
        q=request.args.get("q", ""), verified=verified_param or "",
    )


@orgs_bp.route("/<uuid:org_id>/verify", methods=["POST"])
@permission_required("act.organizations")
def verify(org_id: uuid.UUID):
    OrganizationService(db.session).verify(org_id, current_user.id)
    db.session.commit()
    flash("Organization verified.", "success")
    return redirect(url_for("organizations.list_view"))


@orgs_bp.route("/<uuid:org_id>/unverify", methods=["POST"])
@permission_required("act.organizations")
def unverify(org_id: uuid.UUID):
    OrganizationService(db.session).unverify(org_id, current_user.id)
    db.session.commit()
    flash("Organization unverified.", "success")
    return redirect(url_for("organizations.list_view"))


@orgs_bp.route("/volunteers/pending")
@login_required
def pending_volunteers():
    svc = OrganizationService(db.session)
    return render_template("organizations/volunteers.html",
                           enrollments=svc.pending_volunteers())


@orgs_bp.route("/volunteers/<uuid:enrollment_id>/approve", methods=["POST"])
@permission_required("act.organizations")
def approve_volunteer(enrollment_id: uuid.UUID):
    OrganizationService(db.session).approve_volunteer(enrollment_id, current_user.id)
    db.session.commit()
    flash("Volunteer approved.", "success")
    return redirect(url_for("organizations.pending_volunteers"))

