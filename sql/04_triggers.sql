-- =============================================================================
--  IDRM MVP — 04_triggers.sql
--  Append-only enforcement + updated_at maintenance.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- The audit table is append-only.  Any UPDATE or DELETE raises.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION block_audit_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only — UPDATE and DELETE are forbidden';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_immutable ON audit_logs;
CREATE TRIGGER trg_audit_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION block_audit_mutation();

-- ---------------------------------------------------------------------------
-- updated_at maintenance on every mutable row.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to every table that has an updated_at column and allows updates.
DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY[
        'users', 'organizations', 'resources', 'incidents',
        'notification_preferences', 'auto_approval_policies',
        'entity_lists', 'regions', 'units', 'unit_statuses',
        'personnel_statuses', 'inventory_items', 'trainings',
        'shifts', 'bigboard_configs'
    ])
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_touch_%1$s ON %1$I', t);
        EXECUTE format(
            'CREATE TRIGGER trg_touch_%1$s BEFORE UPDATE ON %1$I '
            'FOR EACH ROW EXECUTE FUNCTION set_updated_at();', t);
    END LOOP;
END;
$$;
