"""baseline: PostGIS + 29 core tables + indexes + triggers

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _enum(name: str, *values: str) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()

    # ---- extensions -------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")

    # ---- enums ------------------------------------------------------------
    for name, values in [
        ("user_role", ("citizen","provider","coordinator","admin")),
        ("user_status", ("pending","active","suspended","deactivated")),
        ("org_type", ("ngo","government","private","hospital","volunteer_group")),
        ("service_type", ("medical","food","rescue","water","shelter","other")),
        ("priority", ("low","medium","high","critical")),
        ("incident_status", ("created","approved","accepted","in_progress",
                             "completed","verified","cancelled","rejected")),
        ("alert_severity", ("info","warning","critical")),
        ("notification_type", ("incident_update","assignment","alert","verification","system")),
        ("file_purpose", ("incident_photo","completion_proof","org_document","training_material")),
        ("applies_to", ("incident","provider")),
        ("decision_kind", ("approved","rejected","deferred","skipped")),
        ("decision_reason", ("matched_policy","no_policy_matched","cap_exceeded",
                             "region_mismatch","disabled","redis_unavailable",
                             "invalid_policy","outside_known_region","entity_blocked")),
        ("list_type", ("blocklist","allowlist","watchlist")),
        ("list_effect", ("hard_block","soft_block","allow_override","observe")),
        ("entity_type", ("user_id","email","phone","ip_address",
                         "device_fingerprint","organization_id","region_id")),
        ("identity_type", ("user","ip","session","anonymous")),
        ("login_outcome", ("success","bad_password","unknown_user","locked","disabled","blocked")),
        ("enrollment_scope", ("organization","event","region","service")),
        ("enrollment_status", ("pending","active","suspended","completed","rejected")),
        ("org_member_role", ("owner","coordinator","member")),
        ("delivery_channel", ("email","sms","in_app","webhook")),
        ("delivery_status", ("queued","sent","failed","abandoned")),
    ]:
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    # ---- users ------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("role", _enum("user_role"), nullable=False, server_default="citizen"),
        sa.Column("status", _enum("user_status"), nullable=False, server_default="pending"),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True)),
        sa.Column("failed_login_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("last_active_at", sa.DateTime(timezone=True)),
        sa.Column("token_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("trust_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("preferences", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(128), nullable=False),
        sa.Column("refresh_token_family", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_version_at_issue", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("device_fingerprint", sa.String(64)),
        sa.Column("login_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("flagged_at", sa.DateTime(timezone=True)),
        sa.Column("flag_reason", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "password_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "login_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("outcome", _enum("login_outcome"), nullable=False),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("device_fingerprint", sa.String(64)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # ---- regions, organizations, resources -------------------------------
    op.create_table(
        "regions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("boundary", Geometry("MULTIPOLYGON", srid=4326), nullable=False),
        sa.Column("parent_region_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("regions.id")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", _enum("org_type"), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("parent_organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id")),
        sa.Column("service_categories", postgresql.ARRAY(_enum("service_type")),
                  nullable=False, server_default=sa.text("'{}'")),
        sa.Column("service_area_center", Geometry("POINT", srid=4326)),
        sa.Column("service_radius_km", sa.Numeric(8, 2), nullable=False, server_default="10.0"),
        sa.Column("capacity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("available_capacity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_available", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("verified_region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id")),
        sa.Column("rating", sa.Numeric(3, 2)),
        sa.Column("total_requests_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("contact_phone", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", _enum("org_member_role"), nullable=False),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )

    op.create_table(
        "resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(50)),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("location", Geometry("POINT", srid=4326)),
        sa.Column("is_available", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )

    # ---- incidents, alerts, notifications, files -------------------------
    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("service_type", _enum("service_type"), nullable=False),
        sa.Column("priority", _enum("priority"), nullable=False),
        sa.Column("status", _enum("incident_status"), nullable=False, server_default="created"),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("location", Geometry("POINT", srid=4326), nullable=False),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id")),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("guest_contact", sa.String(20)),
        sa.Column("tracking_token", sa.String(64), unique=True),
        sa.Column("assigned_organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id")),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("auto_approved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("auto_policy_id", postgresql.UUID(as_uuid=True)),
        sa.Column("rating", sa.SmallInteger),
        sa.Column("review", sa.Text),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("cancellation_reason", sa.Text),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_incidents_rating_range"),
    )

    op.create_table(
        "incident_updates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", _enum("incident_status")),
        sa.Column("to_status", _enum("incident_status"), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("severity", _enum("alert_severity"), nullable=False),
        sa.Column("area", Geometry("MULTIPOLYGON", srid=4326)),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id")),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("type", _enum("notification_type"), nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("link", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "notification_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("email", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("sms", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("in_app", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", _enum("delivery_channel"), nullable=False),
        sa.Column("status", _enum("delivery_status"), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        sa.Column("provider_message_id", sa.String(255)),
        sa.Column("attempted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("bucket", sa.String(63), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("url", sa.String(1024)),
        sa.Column("content_type", sa.String(100)),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column("purpose", _enum("file_purpose"), nullable=False),
        sa.Column("entity_type", sa.String(30)),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("size_bytes <= 10485760", name="ck_files_size_max"),
    )

    # ---- governance -------------------------------------------------------
    op.create_table(
        "auto_approval_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("applies_to", _enum("applies_to"), nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("parent_policy_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("auto_approval_policies.id")),
        sa.Column("region_scope", postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
                  nullable=False, server_default=sa.text("'{}'")),
        sa.Column("service_types", postgresql.ARRAY(_enum("service_type")),
                  nullable=False, server_default=sa.text("'{}'")),
        sa.Column("priorities_allowed", postgresql.ARRAY(_enum("priority")),
                  nullable=False, server_default=sa.text("'{}'")),
        sa.Column("conditions", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("caps", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "auto_approval_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("subject_type", _enum("applies_to"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("auto_approval_policies.id")),
        sa.Column("decision", _enum("decision_kind"), nullable=False),
        sa.Column("reason", _enum("decision_reason"), nullable=False),
        sa.Column("evaluated_conditions", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("counters_at_decision", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regions.id")),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("overridden_at", sa.DateTime(timezone=True)),
        sa.Column("overridden_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("override_reason", sa.Text),
        sa.UniqueConstraint("subject_type", "subject_id", name="uq_decision_subject"),
    )

    op.create_table(
        "entity_lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", _enum("entity_type"), nullable=False),
        sa.Column("entity_value", sa.Text, nullable=False),
        sa.Column("list_type", _enum("list_type"), nullable=False),
        sa.Column("effect", _enum("list_effect"), nullable=False),
        sa.Column("scope", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("reason", sa.Text),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "entity_list_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("list_entry_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("entity_lists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", _enum("entity_type"), nullable=False),
        sa.Column("entity_value", sa.Text, nullable=False),
        sa.Column("subject_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("effect", _enum("list_effect"), nullable=False),
        sa.Column("context", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "rate_limit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("bucket", sa.String(64), nullable=False),
        sa.Column("identity", sa.String(255), nullable=False),
        sa.Column("identity_type", _enum("identity_type"), nullable=False),
        sa.Column("allowed", sa.Boolean, nullable=False),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "volunteer_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_type", _enum("enrollment_scope"), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True)),
        sa.Column("status", _enum("enrollment_status"), nullable=False, server_default="pending"),
        sa.Column("self_enrolled_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.Column("rejection_reason", sa.Text),
        sa.UniqueConstraint("user_id", "scope_type", "scope_id", name="uq_volunteer_scope"),
    )

    op.create_table(
        "user_delegations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_type", _enum("enrollment_scope"), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True)),
        sa.Column("can_approve_volunteers", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("can_approve_incidents", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "mutual_aid_agreements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("from_org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("auto_accept", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("max_personnel", sa.Integer),
        sa.Column("max_units", sa.Integer),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("from_org_id <> to_org_id"),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("scopes", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("secret_hash", sa.String(128), nullable=False),
        sa.Column("events", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("status", _enum("delivery_status"), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("response_status", sa.Integer),
        sa.Column("error", sa.Text),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "geocode_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("lat_rounded", sa.Numeric(7, 5), nullable=False),
        sa.Column("lng_rounded", sa.Numeric(7, 5), nullable=False),
        sa.Column("formatted_address", sa.Text),
        sa.Column("provider", sa.String(32)),
        sa.Column("raw", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("lat_rounded", "lng_rounded", name="uq_geocode_rounded"),
    )

    # ---- audit ------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50)),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("old_values", postgresql.JSONB),
        sa.Column("new_values", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # ---- indexes ----------------------------------------------------------
    op.execute("CREATE INDEX ix_incidents_location ON incidents USING GIST (location);")
    op.execute("CREATE INDEX ix_orgs_service_area ON organizations USING GIST (service_area_center);")
    op.execute("CREATE INDEX ix_resources_location ON resources USING GIST (location);")
    op.execute("CREATE INDEX ix_alerts_area ON alerts USING GIST (area);")
    op.execute("CREATE INDEX ix_regions_boundary ON regions USING GIST (boundary);")

    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_status_created", "incidents",
                    ["status", sa.text("created_at DESC")])
    op.create_index("ix_incidents_service_type", "incidents", ["service_type"])
    op.create_index("ix_incidents_priority", "incidents", ["priority"])
    op.create_index("ix_incidents_requester", "incidents", ["requester_id"])
    op.create_index("ix_incidents_assigned_org", "incidents", ["assigned_organization_id"])
    op.create_index("ix_incidents_region", "incidents", ["region_id"])

    op.create_index("ix_user_sessions_session_id", "user_sessions", ["session_id"])
    op.create_index("ix_user_sessions_family", "user_sessions", ["refresh_token_family"])
    op.execute("CREATE INDEX ix_user_sessions_active ON user_sessions (user_id, expires_at) "
               "WHERE revoked_at IS NULL;")

    op.create_index("ix_policies_active_applies", "auto_approval_policies",
                    ["applies_to", "active", "priority"])
    op.execute("CREATE INDEX ix_policies_region_scope ON auto_approval_policies "
               "USING GIN (region_scope);")
    op.execute("CREATE INDEX ix_policies_service_types ON auto_approval_policies "
               "USING GIN (service_types);")
    op.create_index("ix_decisions_policy_time", "auto_approval_decisions",
                    ["policy_id", sa.text("evaluated_at DESC")])
    op.create_index("ix_decisions_region_time", "auto_approval_decisions",
                    ["region_id", sa.text("evaluated_at DESC")])

    op.create_index("ix_entity_lists_lookup", "entity_lists",
                    ["entity_type", "entity_value", "active"])
    op.execute("CREATE INDEX ix_entity_lists_scope ON entity_lists USING GIN (scope);")

    op.create_index("ix_login_attempts_email", "login_attempts",
                    ["email", sa.text("occurred_at DESC")])
    op.create_index("ix_login_attempts_ip", "login_attempts",
                    ["ip_address", sa.text("occurred_at DESC")])

    op.create_index("ix_audit_actor_created", "audit_logs",
                    ["actor_id", sa.text("created_at DESC")])
    op.create_index("ix_audit_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("ix_audit_created_at", "audit_logs", [sa.text("created_at DESC")])

    op.execute("CREATE INDEX ix_users_email_trgm ON users USING GIN (email gin_trgm_ops);")
    op.execute("CREATE INDEX ix_users_name_trgm ON users USING GIN (name gin_trgm_ops);")
    op.execute("CREATE INDEX ix_orgs_name_trgm ON organizations USING GIN (name gin_trgm_ops);")

    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])
    op.create_index("ix_volunteers_status", "volunteer_enrollments", ["status"])
    op.create_index("ix_volunteers_user", "volunteer_enrollments", ["user_id"])

    # ---- triggers ---------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN NEW.updated_at := now(); RETURN NEW; END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION block_audit_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only — UPDATE and DELETE are forbidden';
        END;
        $$ LANGUAGE plpgsql;
    """)

    for table in ("users", "organizations", "resources", "incidents",
                  "notification_preferences", "auto_approval_policies",
                  "entity_lists", "regions"):
        op.execute(f"CREATE TRIGGER trg_touch_{table} BEFORE UPDATE ON {table} "
                   f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();")

    op.execute("CREATE TRIGGER trg_audit_immutable "
               "BEFORE UPDATE OR DELETE ON audit_logs "
               "FOR EACH ROW EXECUTE FUNCTION block_audit_mutation();")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_immutable ON audit_logs;")
    for t in ("regions", "entity_lists", "auto_approval_policies",
              "notification_preferences", "incidents", "resources",
              "organizations", "users"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_touch_{t} ON {t};")
    op.execute("DROP FUNCTION IF EXISTS block_audit_mutation();")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")

    for t in ("audit_logs", "geocode_cache", "webhook_deliveries",
              "webhook_subscriptions", "api_keys", "user_delegations",
              "volunteer_enrollments", "rate_limit_events",
              "entity_list_matches", "entity_lists", "auto_approval_decisions",
              "auto_approval_policies", "mutual_aid_agreements",
              "files", "notification_deliveries", "notification_preferences",
              "notifications", "alerts", "incident_updates", "incidents",
              "resources", "organization_members", "organizations", "regions",
              "login_attempts", "password_history", "email_verification_tokens",
              "password_reset_tokens", "user_sessions", "users"):
        op.drop_table(t)

    for name in ("delivery_status", "delivery_channel", "org_member_role",
                 "enrollment_status", "enrollment_scope", "login_outcome",
                 "identity_type", "entity_type", "list_effect", "list_type",
                 "decision_reason", "decision_kind", "applies_to",
                 "file_purpose", "notification_type", "alert_severity",
                 "incident_status", "priority", "service_type", "org_type",
                 "user_status", "user_role"):
        op.execute(f"DROP TYPE IF EXISTS {name};")
