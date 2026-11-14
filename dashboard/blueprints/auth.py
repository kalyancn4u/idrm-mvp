"""Dashboard authentication — Flask-Login against the shared `users` table."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from dashboard.extensions import DashboardUser, db
from shared.audit import log_sync
from shared.models.identity import User
from shared.security import verify_password

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)


def _reject(user: User | None, email: str, reason: str):
    """Record a failed sign-in and show the same message whatever the reason."""
    log_sync(db.session, actor_id=user.id if user else None,
             action="dashboard.login_failed", resource_type="user",
             resource_id=user.id if user else None,
             new_values={"email": email, "reason": reason})
    db.session.commit()
    flash("Invalid credentials, or your role cannot access the dashboard.", "error")
    return render_template("auth/login.html"), 401


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.overview"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))
        now = datetime.now(UTC)

        user: User | None = (
            db.session.query(User)
            .filter(User.email == email, User.deleted_at.is_(None))
            .one_or_none()
        )
        if user is None:
            return _reject(None, email, "unknown_user")

        # Same lockout the API uses, on the same two columns.
        if user.locked_until and user.locked_until > now:
            return _reject(user, email, "locked")

        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_FAILED_LOGINS:
                user.locked_until = now + LOCKOUT
                user.failed_login_attempts = 0
            return _reject(user, email, "bad_password")

        role = user.role.value if hasattr(user.role, "value") else user.role
        if role not in current_app.config["ALLOWED_DASHBOARD_ROLES"]:
            return _reject(user, email, "role_not_allowed")
        if not user.is_active:
            return _reject(user, email, "not_active")

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        login_user(DashboardUser(user), remember=remember)
        log_sync(db.session, actor_id=user.id, action="dashboard.login",
                 resource_type="user", resource_id=user.id)
        db.session.commit()

        nxt = request.args.get("next")
        if nxt and nxt.startswith("/dashboard") and "//" not in nxt and "\\" not in nxt:
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

