"""Policies, decisions, entity lists."""

from __future__ import annotations

import uuid

from flask import (
    Blueprint, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required

from dashboard.extensions import db
from dashboard.security import admin_required, permission_required
from dashboard.services.policies import PolicyService

policies_bp = Blueprint("policies", __name__, template_folder="../templates")


@policies_bp.route("/")
@login_required
def list_view():
    svc = PolicyService(db.session)
    return render_template("policies/list.html", policies=svc.list_policies())


@policies_bp.route("/<uuid:policy_id>/toggle", methods=["POST"])
@admin_required
def toggle(policy_id: uuid.UUID):
    active = request.form.get("active") == "1"
    PolicyService(db.session).set_active(policy_id, active, current_user.id)
    db.session.commit()
    flash(f"Policy {'activated' if active else 'deactivated'}.", "success")
    return redirect(url_for("policies.list_view"))


@policies_bp.route("/decisions")
@login_required
def decisions():
    page = max(1, int(request.args.get("page", 1)))
    limit = 50
    rows, total = PolicyService(db.session).list_decisions(
        page=page, limit=limit,
        decision=request.args.get("decision") or None,
    )
    return render_template(
        "policies/decisions.html",
        rows=rows, page=page, total=total,
        pages=max(1, (total + limit - 1) // limit),
        decision=request.args.get("decision", ""),
    )


@policies_bp.route("/entity-lists")
@login_required
def entity_lists():
    rows = PolicyService(db.session).list_entity_lists(
        entity_type=request.args.get("entity_type") or None
    )
    return render_template("policies/entity_lists.html", rows=rows)


@policies_bp.route("/entity-lists", methods=["POST"])
@permission_required("act.policies")
def create_entity_list():
    svc = PolicyService(db.session)
    svc.create_entity_list(
        entity_type=request.form["entity_type"],
        entity_value=request.form["entity_value"].strip(),
        list_type=request.form["list_type"],
        effect=request.form["effect"],
        reason=(request.form.get("reason") or "").strip(),
        actor_id=current_user.id,
    )
    db.session.commit()
    flash("List entry created.", "success")
    return redirect(url_for("policies.entity_lists"))

