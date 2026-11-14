"""User management."""

from __future__ import annotations

import uuid

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from dashboard.extensions import db
from dashboard.security import admin_required
from dashboard.services import enum_or_none
from dashboard.services.users import UserService
from shared.enums import UserRole, UserStatus

users_bp = Blueprint("users", __name__, template_folder="../templates")


@users_bp.route("/")
@login_required
def list_view():
    page = max(1, request.args.get("page", 1, type=int))   # non-numbers fall back to 1
    limit = 25
    rows, total = UserService(db.session).list(
        page=page, limit=limit,
        role=enum_or_none(UserRole, request.args.get("role")),
        status=enum_or_none(UserStatus, request.args.get("status")),
        q=(request.args.get("q") or "").strip() or None,
    )
    return render_template(
        "users/list.html",
        rows=rows, page=page, total=total,
        pages=max(1, (total + limit - 1) // limit),
        role=request.args.get("role", ""),
        status=request.args.get("status", ""),
        q=request.args.get("q", ""),
    )


@users_bp.route("/<uuid:user_id>")
@login_required
def detail(user_id: uuid.UUID):
    svc = UserService(db.session)
    user = svc.get(user_id)
    if user is None:
        abort(404)
    return render_template("users/detail.html", user=user,
                           sessions=svc.sessions_for(user_id))


@users_bp.route("/<uuid:user_id>/role", methods=["POST"])
@admin_required
def set_role(user_id: uuid.UUID):
    role = request.form.get("role", "")
    if role not in {"citizen", "provider", "coordinator", "admin"}:
        flash("Invalid role.", "error")
    else:
        UserService(db.session).set_role(user_id, role, current_user.id)
        db.session.commit()
        flash(f"Role changed to {role}.", "success")
    return redirect(url_for("users.detail", user_id=user_id))


@users_bp.route("/<uuid:user_id>/status", methods=["POST"])
@admin_required
def set_status(user_id: uuid.UUID):
    status = request.form.get("status", "")
    if status not in {"pending", "active", "suspended", "deactivated"}:
        flash("Invalid status.", "error")
    else:
        UserService(db.session).set_status(user_id, status, current_user.id)
        db.session.commit()
        flash(f"Status changed to {status}.", "success")
    return redirect(url_for("users.detail", user_id=user_id))


@users_bp.route("/<uuid:user_id>/force-logout", methods=["POST"])
@admin_required
def force_logout(user_id: uuid.UUID):
    UserService(db.session).force_logout(user_id, current_user.id)
    db.session.commit()
    flash("All sessions revoked and tokens invalidated.", "success")
    return redirect(url_for("users.detail", user_id=user_id))

