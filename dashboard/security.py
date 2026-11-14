"""Dashboard RBAC matrix + route guards."""

from __future__ import annotations

from functools import wraps

from flask import abort, flash
from flask_login import current_user, login_required

# Only these roles may sign into the dashboard at all
ALLOWED_LOGIN_ROLES = {"coordinator", "admin"}

PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "view.overview", "view.dispatch", "view.bigboard",
        "view.incidents", "act.incidents",
        "view.personnel", "act.personnel",
        "view.organizations", "act.organizations",
        "view.users", "act.users",
        "view.scheduling", "act.scheduling",
        "view.logistics", "act.logistics",
        "view.ics", "act.ics",
        "view.alerts", "act.alerts",
        "view.policies", "act.policies",
        "view.audit", "view.reports", "export.data",
    },
    "coordinator": {
        "view.overview", "view.dispatch", "view.bigboard",
        "view.incidents", "act.incidents",
        "view.personnel", "act.personnel",
        "view.organizations", "act.organizations",
        "view.users",
        "view.scheduling", "act.scheduling",
        "view.logistics", "act.logistics",
        "view.ics", "act.ics",
        "view.alerts", "act.alerts",
        # Coordinators switch regional auto-approval on and off and manage
        # entity lists. Platform-wide policies stay admin-only (see the
        # policies blueprint).
        "view.policies", "act.policies",
        "view.audit", "view.reports", "export.data",
    },
}


def has_permission(permission: str, user=None) -> bool:
    u = user or current_user
    if not getattr(u, "is_authenticated", False):
        return False
    role = u.role.value if hasattr(u.role, "value") else u.role
    return permission in PERMISSIONS.get(role, set())


def roles_required(*roles: str):
    def deco(view):
        @wraps(view)
        @login_required
        def wrapper(*a, **kw):
            role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
            if role not in roles:
                flash("You do not have permission to view that page.", "error")
                abort(403)
            return view(*a, **kw)

        return wrapper

    return deco


def admin_required(view):
    return roles_required("admin")(view)


def permission_required(permission: str):
    def deco(view):
        @wraps(view)
        @login_required
        def wrapper(*a, **kw):
            if not has_permission(permission):
                flash("You do not have permission to perform that action.", "error")
                abort(403)
            return view(*a, **kw)

        return wrapper

    return deco

