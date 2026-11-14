"""
Flask dashboard — the staff operations console.

Deliberately a peer of `app/`, not nested inside it.
Boundary rule (enforced by `make lint`):
    dashboard/**  may import from shared/**        ✅
    dashboard/**  may NOT import from app/**       ❌
"""

from __future__ import annotations

import logging
import uuid

from flask import Flask, redirect, render_template, request, url_for

from shared.config import get_settings

log = logging.getLogger(__name__)


def create_dashboard() -> Flask:
    """WSGI application factory for the staff console."""
    settings = get_settings()
    settings.require_safe_for_production()

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/dashboard/static",
    )

    app.config.update(
        SECRET_KEY=settings.dashboard_secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.dashboard_session_cookie_secure,
        PERMANENT_SESSION_LIFETIME=60 * settings.dashboard_session_lifetime_minutes,
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_TIME_LIMIT=None,
        ALLOWED_DASHBOARD_ROLES=settings.dashboard_roles,
        APP_NAME=settings.app_name,
        APP_TAGLINE=settings.app_tagline,
        ENV=settings.app_env,
    )

    # ---- extensions -------------------------------------------------------
    from dashboard.extensions import csrf, init_app, login_manager

    init_app(app)  # registers the request-scoped DB session teardown
    login_manager.init_app(app)
    csrf.init_app(app)

    # ---- blueprints -------------------------------------------------------
    from dashboard.blueprints.alerts import alerts_bp
    from dashboard.blueprints.audit import audit_bp
    from dashboard.blueprints.auth import auth_bp
    from dashboard.blueprints.bigboard import bigboard_bp
    from dashboard.blueprints.dispatch import dispatch_bp
    from dashboard.blueprints.ics import ics_bp
    from dashboard.blueprints.incidents import incidents_bp
    from dashboard.blueprints.logistics import logistics_bp
    from dashboard.blueprints.main import main_bp
    from dashboard.blueprints.organizations import orgs_bp
    from dashboard.blueprints.personnel import personnel_bp
    from dashboard.blueprints.policies import policies_bp
    from dashboard.blueprints.reports import reports_bp
    from dashboard.blueprints.scheduling import scheduling_bp
    from dashboard.blueprints.users import users_bp

    app.register_blueprint(auth_bp,         url_prefix="/dashboard/auth")
    app.register_blueprint(main_bp,         url_prefix="/dashboard")
    app.register_blueprint(dispatch_bp,     url_prefix="/dashboard/dispatch")
    app.register_blueprint(bigboard_bp,     url_prefix="/dashboard/bigboard")
    app.register_blueprint(incidents_bp,    url_prefix="/dashboard/incidents")
    app.register_blueprint(personnel_bp,    url_prefix="/dashboard/personnel")
    app.register_blueprint(orgs_bp,         url_prefix="/dashboard/organizations")
    app.register_blueprint(users_bp,        url_prefix="/dashboard/users")
    app.register_blueprint(scheduling_bp,   url_prefix="/dashboard/scheduling")
    app.register_blueprint(logistics_bp,    url_prefix="/dashboard/logistics")
    app.register_blueprint(ics_bp,          url_prefix="/dashboard/ics")
    app.register_blueprint(policies_bp,     url_prefix="/dashboard/policies")
    app.register_blueprint(alerts_bp,       url_prefix="/dashboard/alerts")
    app.register_blueprint(audit_bp,        url_prefix="/dashboard/audit")
    app.register_blueprint(reports_bp,      url_prefix="/dashboard/reports")

    @app.route("/dashboard")
    def _no_slash():
        return redirect(url_for("main.overview"))

    # ---- request context (for logs and audit rows) -------------------------
    if settings.trust_forwarded_for:
        # Behind a proxy we control: take the client address and scheme from
        # the headers that proxy sets.
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    @app.before_request
    def _request_context():
        from shared.logging import client_ip_ctx, request_id_ctx

        request_id_ctx.set((request.headers.get("X-Request-ID") or uuid.uuid4().hex)[:64])
        client_ip_ctx.set(request.remote_addr or "-")

    # ---- security headers -------------------------------------------------
    @app.after_request
    def _headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
            "https://unpkg.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https://*.tile.openstreetmap.org https://unpkg.com; "
            "script-src 'self' https://unpkg.com; "
            "connect-src 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'",
        )
        return response

    # ---- context ----------------------------------------------------------
    @app.context_processor
    def _inject():
        from datetime import UTC, datetime

        from flask_login import current_user

        return {
            "app_name": settings.app_name,
            "app_tagline": settings.app_tagline,
            "now_utc": datetime.now(UTC),
            "current_year": datetime.now(UTC).year,
            "current_user": current_user,
        }

    # ---- errors -----------------------------------------------------------
    @app.errorhandler(403)
    def _forbidden(_):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def _not_found(_):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def _server(_):
        from dashboard.extensions import db as _db

        _db.session.rollback()
        return render_template("errors/500.html"), 500

    log.info("Dashboard app created (env=%s)", settings.app_env)
    return app

