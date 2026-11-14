"""Resgrid-inspired operational tables.

Revision ID: 0002_resgrid
Revises: 0001_baseline
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision = "0002_resgrid"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def _enum(name: str, *values: str) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    # enums
    for name, values in [
        ("personnel_status", ("available","responding","on_scene","transporting","at_hospital","returning","unavailable","off_duty")),
        ("unit_status", ("in_quarters","dispatched","en_route","on_scene","transporting","at_hospital","returning","out_of_service","unavailable")),
        ("shift_type", ("assigned","signup")),
        ("trade_status", ("pending","accepted","rejected","cancelled","expired")),
        ("certification_status", ("active","expiring","expired","revoked")),
        ("training_status", ("assigned","in_progress","completed","overdue","expired")),
        ("inventory_kind", ("perishable","durable")),
        ("inventory_txn_type", ("receipt","issue","transfer","adjustment","return","disposal")),
        ("ics_lane_type", ("division","group","branch","sector","strike_team","task_force","staging","unified_command")),
        ("ics_role", ("incident_commander","operations","planning","logistics","finance","safety","public_information","liaison","division_supervisor","group_supervisor","branch_director","strike_team_leader","task_force_leader","staging_area_manager","resource_unit_leader")),
        ("dispatch_offer_status", ("pending","accepted","declined","expired","cancelled")),
        ("chat_channel_type", ("peer_to_peer","group","dispatch_to_unit","command")),
        ("run_log_type", ("incident","training","meeting","event","other")),
    ]:
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    # ---- personnel ----
    op.create_table("personnel_statuses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", _enum("personnel_status"), nullable=False, server_default="off_duty"),
        sa.Column("staffing_level", sa.Integer, nullable=False, server_default="0"),
        sa.Column("note", sa.Text),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("location", Geometry("POINT", srid=4326)),
        sa.Column("available_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("personnel_status_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", _enum("personnel_status")),
        sa.Column("to_status", _enum("personnel_status"), nullable=False),
        sa.Column("staffing_level", sa.Integer),
        sa.Column("note", sa.Text),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="SET NULL")),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("units",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(50)),
        sa.Column("callsign", sa.String(32)),
        sa.Column("capacity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("home_location", Geometry("POINT", srid=4326)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )

    op.create_table("unit_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("is_lead", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("left_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("unit_id", "user_id"),
    )

    op.create_table("unit_statuses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", _enum("unit_status"), nullable=False, server_default="in_quarters"),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="SET NULL")),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("location", Geometry("POINT", srid=4326)),
        sa.Column("note", sa.Text),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("unit_status_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", _enum("unit_status")),
        sa.Column("to_status", _enum("unit_status"), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="SET NULL")),
        sa.Column("note", sa.Text),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ---- scheduling ----
    op.create_table("shifts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("shift_type", _enum("shift_type"), nullable=False, server_default="signup"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("min_personnel", sa.Integer, nullable=False, server_default="1"),
        sa.Column("max_personnel", sa.Integer),
        sa.Column("required_roles", postgresql.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("required_certs", postgresql.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("location", Geometry("POINT", srid=4326)),
        sa.Column("notes", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("ends_at > starts_at"),
    )

    op.create_table("shift_signups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("shift_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signed_up_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("attended", sa.Boolean),
        sa.Column("attendance_note", sa.Text),
        sa.UniqueConstraint("shift_id", "user_id"),
    )

    op.create_table("shift_trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("shift_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requesting_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", _enum("trade_status"), nullable=False, server_default="pending"),
        sa.Column("reason", sa.Text),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("personnel_certifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("issued_by", sa.String(255)),
        sa.Column("issued_at", sa.Date),
        sa.Column("expires_at", sa.Date),
        sa.Column("status", _enum("certification_status"), nullable=False, server_default="active"),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "code"),
    )

    # ---- trainings ----
    op.create_table("trainings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("content", sa.Text),
        sa.Column("attachments", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("quiz", postgresql.JSONB),
        sa.Column("passing_score", sa.Integer),
        sa.Column("validity_months", sa.Integer),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", "code"),
    )

    op.create_table("training_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("training_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("status", _enum("training_status"), nullable=False, server_default="assigned"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.UniqueConstraint("training_id", "user_id"),
    )

    op.create_table("training_completions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer),
        sa.Column("passed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.Date),
        sa.Column("notes", sa.Text),
    )

    # ---- logistics ----
    op.create_table("inventory_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(50)),
        sa.Column("address", sa.Text),
        sa.Column("location", Geometry("POINT", srid=4326)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("inventory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_locations.id", ondelete="SET NULL")),
        sa.Column("sku", sa.String(64)),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", _enum("inventory_kind"), nullable=False),
        sa.Column("unit_of_measure", sa.String(32)),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("serial_number", sa.String(128)),
        sa.Column("barcode", sa.String(128)),
        sa.Column("expires_at", sa.Date),
        sa.Column("condition", sa.String(32)),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("inventory_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("txn_type", _enum("inventory_txn_type"), nullable=False),
        sa.Column("quantity_delta", sa.Integer, nullable=False),
        sa.Column("from_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_locations.id", ondelete="SET NULL")),
        sa.Column("to_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_locations.id", ondelete="SET NULL")),
        sa.Column("from_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("to_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="SET NULL")),
        sa.Column("note", sa.Text),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ---- ICS ----
    op.create_table("incident_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commander_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ics_role", _enum("ics_role"), nullable=False, server_default="incident_commander"),
        sa.Column("objectives", sa.Text),
        sa.Column("safety_message", sa.Text),
        sa.Column("established_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("demobilized_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("incident_id", "commander_id", "ics_role"),
    )

    op.create_table("incident_lanes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_lane_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incident_lanes.id", ondelete="CASCADE")),
        sa.Column("lane_type", _enum("ics_lane_type"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("color", sa.String(32)),
        sa.Column("lead_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("objectives", sa.Text),
        sa.Column("requirements", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("lane_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lane_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incident_lanes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("units.id", ondelete="CASCADE")),
        sa.Column("role", sa.String(64)),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("user_id IS NOT NULL OR unit_id IS NOT NULL"),
    )

    op.create_table("run_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("log_type", _enum("run_log_type"), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="SET NULL")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("run_log_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_log_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("run_logs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("units.id", ondelete="SET NULL")),
        sa.Column("hours", sa.Numeric(6, 2)),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ---- comms ----
    op.create_table("messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("target_roles", postgresql.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("target_groups", postgresql.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("target_users", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("requires_rsvp", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )

    op.create_table("chat_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("channel_type", _enum("chat_channel_type"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE")),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("units.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(255)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )

    op.create_table("chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("attachments", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ---- coordination ----
    op.create_table("calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("event_type", sa.String(50)),
        sa.Column("location", Geometry("POINT", srid=4326)),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("rsvp_required", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("rsvp_deadline", sa.DateTime(timezone=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("event_rsvps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calendar_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("response", sa.String(16), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("event_id", "user_id"),
    )

    op.create_table("mutual_aid_agreements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("from_org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("auto_accept", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("max_personnel", sa.Integer),
        sa.Column("max_units", sa.Integer),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("from_org_id <> to_org_id"),
    )

    op.create_table("bigboard_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(255), nullable=False, server_default="Default"),
        sa.Column("layout", postgresql.JSONB, nullable=False, server_default=sa.text("'{\"columns\":2,\"rowHeight\":200}'::jsonb")),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("bigboard_widgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bigboard_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("widget_type", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("span", sa.Integer, nullable=False, server_default="1"),
        sa.Column("row_span", sa.Integer, nullable=False, server_default="1"),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    # ---- dispatch ----
    op.create_table("dispatch_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("units.id", ondelete="CASCADE")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("note", sa.Text),
        sa.CheckConstraint("unit_id IS NOT NULL OR user_id IS NOT NULL"),
    )

    op.create_table("dispatch_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("units.id", ondelete="CASCADE")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("status", _enum("dispatch_offer_status"), nullable=False, server_default="pending"),
        sa.Column("offered_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("offered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("note", sa.Text),
        sa.CheckConstraint("unit_id IS NOT NULL OR user_id IS NOT NULL"),
    )

    # ---- indexes ----
    op.execute("CREATE INDEX IF NOT EXISTS ix_personnel_statuses_status ON personnel_statuses(status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_personnel_statuses_location ON personnel_statuses USING GIST (location);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_personnel_status_events_user ON personnel_status_events(user_id, occurred_at DESC);")
    op.create_index("ix_units_org", "units", ["organization_id"])
    op.execute("CREATE INDEX IF NOT EXISTS ix_units_home_location ON units USING GIST (home_location);")
    op.create_index("ix_unit_members_unit", "unit_members", ["unit_id"])
    op.create_index("ix_unit_members_user", "unit_members", ["user_id"])
    op.create_index("ix_unit_statuses_status", "unit_statuses", ["status"])
    op.execute("CREATE INDEX IF NOT EXISTS ix_unit_statuses_location ON unit_statuses USING GIST (location);")
    op.create_index("ix_unit_status_events_unit", "unit_status_events", ["unit_id"])
    op.create_index("ix_shifts_org_time", "shifts", ["organization_id", "starts_at"])
    op.create_index("ix_shift_signups_shift", "shift_signups", ["shift_id"])
    op.create_index("ix_shift_signups_user", "shift_signups", ["user_id"])
    op.create_index("ix_certs_user", "personnel_certifications", ["user_id"])
    op.create_index("ix_trainings_org", "trainings", ["organization_id"])
    op.create_index("ix_training_assignments_user", "training_assignments", ["user_id", "status"])
    op.create_index("ix_inv_items_org", "inventory_items", ["organization_id"])
    op.create_index("ix_inv_items_location", "inventory_items", ["location_id"])
    op.create_index("ix_inv_txns_item", "inventory_transactions", ["item_id", "occurred_at"])
    op.create_index("ix_incident_commands_incident", "incident_commands", ["incident_id"])
    op.create_index("ix_incident_lanes_incident", "incident_lanes", ["incident_id", "display_order"])
    op.create_index("ix_lane_assignments_lane", "lane_assignments", ["lane_id"])
    op.create_index("ix_run_logs_incident", "run_logs", ["incident_id"])
    op.create_index("ix_run_log_entries_log", "run_log_entries", ["run_log_id", "occurred_at"])
    op.create_index("ix_messages_org", "messages", ["organization_id", "sent_at"])
    op.create_index("ix_chat_channels_incident", "chat_channels", ["incident_id"])
    op.create_index("ix_chat_messages_channel", "chat_messages", ["channel_id", "sent_at"])
    op.create_index("ix_calendar_events_org_time", "calendar_events", ["organization_id", "starts_at"])
    op.create_index("ix_event_rsvps_event", "event_rsvps", ["event_id"])
    op.create_index("ix_mutual_aid_orgs", "mutual_aid_agreements", ["from_org_id", "to_org_id"])
    op.create_index("ix_bigboard_configs_user", "bigboard_configs", ["user_id", "is_default"])
    op.create_index("ix_dispatch_assignments_incident", "dispatch_assignments", ["incident_id"])
    op.create_index("ix_dispatch_assignments_unit", "dispatch_assignments", ["unit_id"])
    op.create_index("ix_dispatch_offers_incident", "dispatch_offers", ["incident_id", "status"])
    op.create_index("ix_dispatch_offers_unit", "dispatch_offers", ["unit_id", "status"])


def downgrade() -> None:
    for t in ("dispatch_offers","dispatch_assignments","bigboard_widgets","bigboard_configs",
              "mutual_aid_agreements","event_rsvps","calendar_events","chat_messages",
              "chat_channels","messages","run_log_entries","run_logs","lane_assignments",
              "incident_lanes","incident_commands","inventory_transactions","inventory_items",
              "inventory_locations","training_completions","training_assignments","trainings",
              "personnel_certifications","shift_trades","shift_signups","shifts",
              "unit_status_events","unit_statuses","unit_members","units",
              "personnel_status_events","personnel_statuses"):
        op.drop_table(t)
    for name in ("run_log_type","chat_channel_type","dispatch_offer_status","ics_role",
                 "ics_lane_type","inventory_txn_type","inventory_kind","training_status",
                 "certification_status","trade_status","shift_type","unit_status","personnel_status"):
        op.execute(f"DROP TYPE IF EXISTS {name};")
