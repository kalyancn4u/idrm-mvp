-- =============================================================================
--  IDRM MVP — 05_regions_and_policies.sql
--  Reference data — the regions, the starter policies, the demo entity lists.
--  Idempotent.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- REGIONS — three starter polygons
-- ---------------------------------------------------------------------------
INSERT INTO regions (code, name, boundary) VALUES
    ('IN-TG-HYD', 'Hyderabad Urban',
     ST_GeomFromText('MULTIPOLYGON(((
        78.35 17.35, 78.55 17.35, 78.55 17.45,
        78.35 17.45, 78.35 17.35
     )))', 4326)),
    ('IN-AP-VJA', 'Vijayawada Urban',
     ST_GeomFromText('MULTIPOLYGON(((
        80.60 16.48, 80.72 16.48, 80.72 16.55,
        80.60 16.55, 80.60 16.48
     )))', 4326)),
    ('IN-AP-VTZ', 'Visakhapatnam Urban',
     ST_GeomFromText('MULTIPOLYGON(((
        83.20 17.65, 83.35 17.65, 83.35 17.78,
        83.20 17.78, 83.20 17.65
     )))', 4326))
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- AUTO-APPROVAL POLICIES
-- ---------------------------------------------------------------------------
INSERT INTO auto_approval_policies (
    code, name, description, applies_to, priority,
    region_scope, service_types, priorities_allowed,
    conditions, caps
)
SELECT
    'IN-TG-HYD-FOOD-WATER-LOW',
    'Auto-approve low-stake food & water — Hyderabad',
    'Approves food and water requests with priority low/medium inside Hyderabad.',
    'incident', 10,
    ARRAY[(SELECT id FROM regions WHERE code = 'IN-TG-HYD')],
    ARRAY['food','water']::service_type[],
    ARRAY['low','medium']::priority[],
    '{"max_estimated_cost_inr": 500, "max_per_requester_per_day": 3}'::jsonb,
    '{"per_region_per_day": 500, "per_requester_per_day": 3}'::jsonb
WHERE NOT EXISTS (
    SELECT 1 FROM auto_approval_policies WHERE code = 'IN-TG-HYD-FOOD-WATER-LOW');

INSERT INTO auto_approval_policies (
    code, name, applies_to, priority,
    region_scope, service_types, priorities_allowed, conditions, caps
)
SELECT
    'IN-AP-VJA-FOOD-WATER-LOW',
    'Auto-approve low-stake food & water — Vijayawada',
    'incident', 10,
    ARRAY[(SELECT id FROM regions WHERE code = 'IN-AP-VJA')],
    ARRAY['food','water']::service_type[],
    ARRAY['low','medium']::priority[],
    '{"max_estimated_cost_inr": 500, "max_per_requester_per_day": 3}'::jsonb,
    '{"per_region_per_day": 300, "per_requester_per_day": 3}'::jsonb
WHERE NOT EXISTS (
    SELECT 1 FROM auto_approval_policies WHERE code = 'IN-AP-VJA-FOOD-WATER-LOW');

INSERT INTO auto_approval_policies (
    code, name, applies_to, priority,
    region_scope, service_types, priorities_allowed, conditions, caps
)
SELECT
    'AUTO-VERIFY-NGO-LOW-RISK',
    'Auto-verify low-risk NGO providers',
    'provider', 20,
    ARRAY[]::uuid[],
    ARRAY['food','water','shelter']::service_type[],
    ARRAY[]::priority[],
    '{"max_org_type_risk": "low", "min_service_radius_km": 5, "max_service_radius_km": 100}'::jsonb,
    '{"per_region_per_day": 20}'::jsonb
WHERE NOT EXISTS (
    SELECT 1 FROM auto_approval_policies WHERE code = 'AUTO-VERIFY-NGO-LOW-RISK');

INSERT INTO auto_approval_policies (
    code, name, description, applies_to, priority,
    region_scope, service_types, priorities_allowed,
    conditions, caps, active
)
SELECT
    'REGION-BLACKOUT-VJA',
    'Blackout auto-approval in Vijayawada (inactive by default)',
    'When active, blocks all auto-approval in Vijayawada.',
    'incident', 1,
    ARRAY[(SELECT id FROM regions WHERE code = 'IN-AP-VJA')],
    ARRAY[]::service_type[],
    ARRAY[]::priority[],
    '{"always_reject": true}'::jsonb,
    '{}'::jsonb,
    FALSE
WHERE NOT EXISTS (
    SELECT 1 FROM auto_approval_policies WHERE code = 'REGION-BLACKOUT-VJA');

-- ---------------------------------------------------------------------------
-- DEMO ENTITY LISTS
-- ---------------------------------------------------------------------------
INSERT INTO entity_lists (entity_type, entity_value, list_type, effect, reason, created_by)
SELECT 'email', 'spam@bad.example', 'blocklist', 'hard_block',
       'Confirmed spam requests.',
       (SELECT id FROM users WHERE email = 'admin@idrm.local')
WHERE NOT EXISTS (SELECT 1 FROM entity_lists WHERE entity_value = 'spam@bad.example');

INSERT INTO entity_lists (entity_type, entity_value, list_type, effect, reason, created_by)
SELECT 'ip_address', '203.0.113.42', 'watchlist', 'observe',
       'Multiple failed logins; observing.',
       (SELECT id FROM users WHERE email = 'admin@idrm.local')
WHERE NOT EXISTS (SELECT 1 FROM entity_lists WHERE entity_value = '203.0.113.42');

COMMIT;
