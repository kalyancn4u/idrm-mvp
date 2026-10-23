-- IDRM MVP — extensions and enums. Idempotent.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Core enums
DO $$ BEGIN CREATE TYPE user_role AS ENUM ('citizen','provider','coordinator','admin'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE user_status AS ENUM ('pending','active','suspended','deactivated'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE org_type AS ENUM ('ngo','government','private','hospital','volunteer_group'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE service_type AS ENUM ('medical','food','rescue','water','shelter','other'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE priority AS ENUM ('low','medium','high','critical'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE incident_status AS ENUM ('created','approved','accepted','in_progress','completed','verified','cancelled','rejected'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE alert_severity AS ENUM ('info','warning','critical'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE notification_type AS ENUM ('incident_update','assignment','alert','verification','system'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE file_purpose AS ENUM ('incident_photo','completion_proof','org_document','training_material'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE applies_to AS ENUM ('incident','provider'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE decision_kind AS ENUM ('approved','rejected','deferred','skipped'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE decision_reason AS ENUM ('matched_policy','no_policy_matched','cap_exceeded','region_mismatch','disabled','redis_unavailable','invalid_policy','outside_known_region','entity_blocked'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE list_type AS ENUM ('blocklist','allowlist','watchlist'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE list_effect AS ENUM ('hard_block','soft_block','allow_override','observe'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE entity_type AS ENUM ('user_id','email','phone','ip_address','device_fingerprint','organization_id','region_id'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE identity_type AS ENUM ('user','ip','session','anonymous'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE login_outcome AS ENUM ('success','bad_password','unknown_user','locked','disabled','blocked'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE enrollment_scope AS ENUM ('organization','event','region','service'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE enrollment_status AS ENUM ('pending','active','suspended','completed','rejected'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE org_member_role AS ENUM ('owner','coordinator','member'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE delivery_channel AS ENUM ('email','sms','in_app','webhook'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE delivery_status AS ENUM ('queued','sent','failed','abandoned'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Operational enums (Resgrid-inspired)
DO $$ BEGIN CREATE TYPE personnel_status AS ENUM ('available','responding','on_scene','transporting','at_hospital','returning','unavailable','off_duty'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE unit_status AS ENUM ('in_quarters','dispatched','en_route','on_scene','transporting','at_hospital','returning','out_of_service','unavailable'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE shift_type AS ENUM ('assigned','signup'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE trade_status AS ENUM ('pending','accepted','rejected','cancelled','expired'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE certification_status AS ENUM ('active','expiring','expired','revoked'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE training_status AS ENUM ('assigned','in_progress','completed','overdue','expired'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE inventory_kind AS ENUM ('perishable','durable'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE inventory_txn_type AS ENUM ('receipt','issue','transfer','adjustment','return','disposal'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE ics_lane_type AS ENUM ('division','group','branch','sector','strike_team','task_force','staging','unified_command'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE ics_role AS ENUM ('incident_commander','operations','planning','logistics','finance','safety','public_information','liaison','division_supervisor','group_supervisor','branch_director','strike_team_leader','task_force_leader','staging_area_manager','resource_unit_leader'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE dispatch_offer_status AS ENUM ('pending','accepted','declined','expired','cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE chat_channel_type AS ENUM ('peer_to_peer','group','dispatch_to_unit','command'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE run_log_type AS ENUM ('incident','training','meeting','event','other'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

