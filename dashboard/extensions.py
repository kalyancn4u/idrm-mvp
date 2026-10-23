"""Flask extension singletons and the request-scoped sync session."""

from __future__ import annotations

import uuid
from typing import Any

from flask import g
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

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


@login_manager.user_loader
def load_user(user_id: str) -> Any:
    from shared.models import User

    try:
        uid = uuid.UUID(user_id)
    except (TypeError, ValueError):
        return None
    with SessionLocal() as session:
        return session.get(User, uid)

