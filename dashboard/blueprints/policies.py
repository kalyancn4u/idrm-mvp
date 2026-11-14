"""Policies, decisions, entity lists."""

from __future__ import annotations

import uuid

from flask import (
    Blueprint, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required

from dashboard.extensions import db
from dashboard.security import permission_required
from dashboard.services import enum_or_none
from dashboard.services.policies import PolicyService
from shared.enums import DecisionKind, EntityType, ListEffect, ListType

policies_bp = Blueprint("policies", __name__, template_folder="../templates")


@policies_bp.route("/")
@login_required
def list_view():
    svc = PolicyService(db.session)
    return render_template("policies/list.html", policies=svc.list_policies())


@policies_bp.route("/<uuid:policy_id>/toggle", methods=["POST"])
@permission_required("act.policies")
def toggle(policy_id: uuid.UUID):
    active = request.form.get("active") == "1"
    svc = PolicyService(db.session)
    policy = svc.get_policy(policy_id)
    if policy is None:
        flash("Policy not found.", "error")
        return redirect(url_for("policies.list_view"))
    # A policy with no region covers the whole platform: admin only.
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if role != "admin" and not policy.region_scope:
        flash("Only an administrator can change a platform-wide policy.", "error")
        return redirect(url_for("policies.list_view"))
    svc.set_active(policy_id, active, current_user.id)
    db.session.commit()
    flash(f"Policy {'activated' if active else 'deactivated'}.", "success")
    return redirect(url_for("policies.list_view"))


@policies_bp.route("/decisions")
@login_required
def decisions():
    page = max(1, request.args.get("page", 1, type=int))   # non-numbers fall back to 1
    limit = 50
    rows, total = PolicyService(db.session).list_decisions(
        page=page, limit=limit,
        decision=enum_or_none(DecisionKind, request.args.get("decision")),
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
        entity_type=enum_or_none(EntityType, request.args.get("entity_type"))
    )
    return render_template("policies/entity_lists.html", rows=rows)


@policies_bp.route("/entity-lists", methods=["POST"])
@permission_required("act.policies")
def create_entity_list():
    entity_type = enum_or_none(EntityType, request.form.get("entity_type"))
    list_type = enum_or_none(ListType, request.form.get("list_type"))
    effect = enum_or_none(ListEffect, request.form.get("effect"))
    entity_value = (request.form.get("entity_value") or "").strip()
    if not (entity_type and list_type and effect and entity_value):
        flash("Choose an entity type, list type and effect, and enter a value.", "error")
        return redirect(url_for("policies.entity_lists"))

    svc = PolicyService(db.session)
    svc.create_entity_list(
        entity_type=entity_type.value,
        entity_value=entity_value,
        list_type=list_type.value,
        effect=effect.value,
        reason=(request.form.get("reason") or "").strip(),
        actor_id=current_user.id,
    )
    db.session.commit()
    flash("List entry created.", "success")
    return redirect(url_for("policies.entity_lists"))

