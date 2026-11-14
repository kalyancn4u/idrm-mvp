"""seed the first admin user (idempotent data migration)

Revision ID: 0003_seed_admin
Revises: 0002_resgrid
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext

from shared.config import get_settings

revision = "0003_seed_admin"
down_revision = "0002_resgrid"
branch_labels = None
depends_on = None

ADMIN_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
ADMIN_EMAIL = "admin@idrm.local"
# Development-only default. It is printed in the README, so it must never be
# the password of a real deployment: set ADMIN_INITIAL_PASSWORD instead.
DEV_ADMIN_PASSWORD = "Admin#2026"


def _admin_password() -> str:
    # Read through Settings so a value in `.env` counts, not only a real
    # environment variable.
    settings = get_settings()
    supplied = settings.admin_initial_password
    if supplied:
        if len(supplied) < 12:
            raise RuntimeError("ADMIN_INITIAL_PASSWORD must be at least 12 characters.")
        return supplied
    if settings.is_production:
        raise RuntimeError(
            "Refusing to create the admin account with the public development "
            "password. Set ADMIN_INITIAL_PASSWORD and run the migration again."
        )
    return DEV_ADMIN_PASSWORD

_pwd = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM users WHERE email = :e"), {"e": ADMIN_EMAIL}
    ).scalar()
    if exists:
        return
    password = _admin_password()
    conn.execute(
        sa.text(
            """
            INSERT INTO users (id, email, password_hash, name, role, status,
                               email_verified, language)
            VALUES (:id, :email, :pw, 'Platform Administrator', 'admin',
                    'active', true, 'en')
            """
        ),
        {"id": ADMIN_ID, "email": ADMIN_EMAIL, "pw": _pwd.hash(password)},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM users WHERE email = :e"), {"e": ADMIN_EMAIL}
    )
