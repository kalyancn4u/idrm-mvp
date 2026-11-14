"""Flask extension singletons and the request-scoped sync session."""

from __future__ import annotations

import uuid
from typing import Any

from flask import g
from flask_login import LoginManager, UserMixin
from flask_wtf.csrf import CSRFProtect

from shared.config import get_settings
from shared.db import SessionLocal

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to access the dashboard."
login_manager.login_message_category = "info"
login_manager.session_protection = "strong"

csrf = CSRFProtect()


class _DbProxy:
    """Flask-friendly facade over a sync SQLAlchemy session."""

    @property
    def session(self):
        if "dash_db_session" not in g:
            g.dash_db_session = SessionLocal()
        return g.dash_db_session

    def close(self) -> None:
        session = g.pop("dash_db_session", None)
        if session is not None:
            session.close()


db = _DbProxy()


def init_app(app) -> None:
    app.teardown_appcontext(_teardown)


def _teardown(exc: BaseException | None = None) -> None:
    if exc:
        try:
            db.session.rollback()
        except Exception:
            pass
    db.close()


class DashboardUser(UserMixin):
    """
    Flask-Login view of a `shared.models.User`.

    Flask-Login needs `get_id()`, `is_authenticated` and `is_anonymous` on the
    object it tracks. The ORM model lives in `shared/` and must stay free of
    Flask, so those are supplied here and every other attribute (`id`, `name`,
    `role`, `initials`, …) is read straight from the wrapped user.
    """

    def __init__(self, user: Any) -> None:
        self._user = user

    def get_id(self) -> str:
        return str(self._user.id)

    @property
    def is_active(self) -> bool:
        return bool(self._user.is_active)

    def __getattr__(self, name: str) -> Any:
        # Only called when normal lookup fails, i.e. for the model's fields.
        if name == "_user":
            raise AttributeError(name)
        return getattr(self._user, name)


@login_manager.user_loader
def load_user(user_id: str) -> Any:
    from shared.models import User

    try:
        uid = uuid.UUID(user_id)
    except (TypeError, ValueError):
        return None
    with SessionLocal() as session:
        user = session.get(User, uid)
    # Runs on every request. Returning None signs the browser out, so a user
    # who was suspended, deleted or demoted loses console access at once
    # instead of keeping it until their cookie expires.
    if user is None or not user.is_active:
        return None
    role = user.role.value if hasattr(user.role, "value") else user.role
    if role not in get_settings().dashboard_roles:
        return None
    return DashboardUser(user)

