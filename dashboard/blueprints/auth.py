"""Dashboard authentication — Flask-Login against the shared `users` table."""

from __future__ import annotations

from datetime import UTC, datetime

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from dashboard.extensions import db
from shared.audit import log_sync
from shared.models.identity import User
from shared.security import verify_password

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.overview"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user: User | None = (
            db.session.query(User)
            .filter(User.email == email, User.deleted_at.is_(None))
            .one_or_none()
        )

        allowed = current_app.config["ALLOWED_DASHBOARD_ROLES"]
        role = (user.role.value if user and hasattr(user.role, "value") else user.role) if user else None

        if (user is None
                or not verify_password(password, user.password_hash)
                or role not in allowed
                or user.status != "active"):
            log_sync(db.session, actor_id=user.id if user else None,
                     action="dashboard.login_failed", resource_type="user",
                     resource_id=user.id if user else None,
                     new_values={"email": email})
            db.session.commit()
            flash("Invalid credentials, or your role cannot access the dashboard.", "error")
            return render_template("auth/login.html"), 401

        login_user(user, remember=remember)
        user.last_login_at = datetime.now(UTC)
        db.session.commit()

        log_sync(db.session, actor_id=user.id, action="dashboard.login",
                 resource_type="user", resource_id=user.id)
        db.session.commit()

        nxt = request.args.get("next")
        if nxt and nxt.startswith("/dashboard"):
            return redirect(nxt)
        return redirect(url_for("main.overview"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    log_sync(db.session, actor_id=current_user.id, action="dashboard.logout",
             resource_type="user", resource_id=current_user.id)
    db.session.commit()
    logout_user()
    flash("Signed out.", "success")
    return redirect(url_for("auth.login"))

