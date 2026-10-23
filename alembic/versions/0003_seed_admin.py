"""seed the first admin user (idempotent data migration)

Revision ID: 0003_seed_admin
Revises: 0002_resgrid
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext

revision = "0003_seed_admin"
down_revision = "0002_resgrid"
branch_labels = None
depends_on = None

ADMIN_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
ADMIN_EMAIL = "admin@idrm.local"
ADMIN_PASSWORD = "Admin#2026"

_pwd = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM users WHERE email = :e"), {"e": ADMIN_EMAIL}
    ).scalar()
    if exists:
        return
    conn.execute(
        sa.text(
            """
            INSERT INTO users (id, email, password_hash, name, role, status,
                               email_verified, language)
            VALUES (:id, :email, :pw, 'Platform Administrator', 'admin',
                    'active', true, 'en')
            """
        ),
        {"id": ADMIN_ID, "email": ADMIN_EMAIL, "pw": _pwd.hash(ADMIN_PASSWORD)},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM users WHERE email = :e"), {"e": ADMIN_EMAIL}
    )
