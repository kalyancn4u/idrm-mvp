"""updated_at triggers for the operational tables

Migration 0001 attached the `set_updated_at()` trigger to its own tables.
Migration 0002 added more tables with an `updated_at` column but never
attached the trigger, so on those tables the column kept its creation time.

Revision ID: 0004_touch_triggers
Revises: 0003_seed_admin
"""
from __future__ import annotations

from alembic import op

revision = "0004_touch_triggers"
down_revision = "0003_seed_admin"
branch_labels = None
depends_on = None

TABLES = (
    "units", "unit_statuses", "personnel_statuses", "inventory_items",
    "trainings", "shifts", "bigboard_configs",
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_touch_{table} ON {table};")
        op.execute(
            f"CREATE TRIGGER trg_touch_{table} BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_touch_{table} ON {table};")
