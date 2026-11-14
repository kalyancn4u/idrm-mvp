-- =============================================================================
--  IDRM MVP — 06_sample_data.sql
--  Rich demo dataset for a fresh database.
--  Idempotent via NOT EXISTS guards.
--
--  NOTE:  The canonical seeding path is `python -m scripts.seed`, which is
--  what `make seed` invokes.  This file is provided for DBAs and auditors who
--  prefer to seed from plain SQL.
--
--  All users share the bcrypt hash of:  IDRMseed#2026
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- USERS
-- ---------------------------------------------------------------------------
INSERT INTO users (id, email, password_hash, name, phone, role, status,
                   email_verified, language)
VALUES
    ('10000000-0000-4000-8000-000000000001',
     'admin@idrm.local',
     '$2b$12$WJxA.L56fhA6KPySlCFIE.3sFCo9ZjaOn0pXduGDdaC8UVGz5xNr.',
     'Platform Administrator', '+91-9000000001', 'admin', 'active', TRUE, 'en'),
    ('10000000-0000-4000-8000-000000000002',
     'coord.hyd@idrm.local',
     '$2b$12$WJxA.L56fhA6KPySlCFIE.3sFCo9ZjaOn0pXduGDdaC8UVGz5xNr.',
     'Anjali Rao (Coordinator, Hyderabad)', '+91-9000000002',
     'coordinator', 'active', TRUE, 'en'),
    ('10000000-0000-4000-8000-000000000003',
     'coord.vja@idrm.local',
     '$2b$12$WJxA.L56fhA6KPySlCFIE.3sFCo9ZjaOn0pXduGDdaC8UVGz5xNr.',
     'Kiran Reddy (Coordinator, Vijayawada)', '+91-9000000003',
     'coordinator', 'active', TRUE, 'te'),
    ('10000000-0000-4000-8000-000000000004',
     'priya.citizen@example.com',
     '$2b$12$WJxA.L56fhA6KPySlCFIE.3sFCo9ZjaOn0pXduGDdaC8UVGz5xNr.',
     'Priya Sharma', '+91-9000000004', 'citizen', 'active', TRUE, 'hi'),
    ('10000000-0000-4000-8000-000000000005',
     'mohan.citizen@example.com',
     '$2b$12$WJxA.L56fhA6KPySlCFIE.3sFCo9ZjaOn0pXduGDdaC8UVGz5xNr.',
     'Mohan Kumar', '+91-9000000005', 'citizen', 'active', TRUE, 'te'),
    ('10000000-0000-4000-8000-000000000006',
     'sneha.citizen@example.com',
     '$2b$12$WJxA.L56fhA6KPySlCFIE.3sFCo9ZjaOn0pXduGDdaC8UVGz5xNr.',
     'Sneha Iyer', '+91-9000000006', 'citizen', 'active', TRUE, 'en'),
    ('10000000-0000-4000-8000-000000000007',
     'smilinghearts@ngo.example',
     '$2b$12$WJxA.L56fhA6KPySlCFIE.3sFCo9ZjaOn0pXduGDdaC8UVGz5xNr.',
     'Smiling Hearts Foundation', '+91-9000000007', 'provider', 'active', TRUE, 'en'),
    ('10000000-0000-4000-8000-000000000008',
     'apmedical@org.example',
     '$2b$12$WJxA.L56fhA6KPySlCFIE.3sFCo9ZjaOn0pXduGDdaC8UVGz5xNr.',
     'AP Medical Response', '+91-9000000008', 'provider', 'active', TRUE, 'te'),
    ('10000000-0000-4000-8000-000000000009',
     'volunteer.ravi@example.com',
     '$2b$12$WJxA.L56fhA6KPySlCFIE.3sFCo9ZjaOn0pXduGDdaC8UVGz5xNr.',
     'Ravi Teja (Volunteer)', '+91-9000000009', 'provider', 'active', TRUE, 'te'),
    ('10000000-0000-4000-8000-00000000000a',
     'volunteer.fatima@example.com',
     '$2b$12$WJxA.L56fhA6KPySlCFIE.3sFCo9ZjaOn0pXduGDdaC8UVGz5xNr.',
     'Fatima Khan (Volunteer)', '+91-9000000010', 'provider', 'active', TRUE, 'hi')
ON CONFLICT (email) DO NOTHING;

-- ---------------------------------------------------------------------------
-- ORGANIZATIONS
-- ---------------------------------------------------------------------------
INSERT INTO organizations (
    id, name, type, owner_user_id, service_categories,
    service_area_center, service_radius_km, capacity, available_capacity,
    is_verified, verified_by, verified_at, contact_phone
)
SELECT
    '20000000-0000-4000-8000-000000000001', 'Smiling Hearts Foundation', 'ngo',
    (SELECT id FROM users WHERE email = 'smilinghearts@ngo.example'),
    ARRAY['food','water']::service_type[],
    ST_GeomFromText('POINT(78.48 17.38)', 4326), 25.0, 500, 420,
    TRUE, (SELECT id FROM users WHERE email = 'admin@idrm.local'),
    now() - INTERVAL '30 days', '+91-9000000007'
WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE name = 'Smiling Hearts Foundation');

INSERT INTO organizations (
    id, name, type, owner_user_id, service_categories,
    service_area_center, service_radius_km, capacity, available_capacity,
    is_verified, verified_by, verified_at, contact_phone
)
SELECT
    '20000000-0000-4000-8000-000000000002', 'AP Medical Response', 'hospital',
    (SELECT id FROM users WHERE email = 'apmedical@org.example'),
    ARRAY['medical','rescue']::service_type[],
    ST_GeomFromText('POINT(80.65 16.51)', 4326), 40.0, 200, 145,
    TRUE, (SELECT id FROM users WHERE email = 'admin@idrm.local'),
    now() - INTERVAL '20 days', '+91-9000000008'
WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE name = 'AP Medical Response');

-- ---------------------------------------------------------------------------
-- ORGANIZATION MEMBERS
-- ---------------------------------------------------------------------------
INSERT INTO organization_members (organization_id, user_id, role, added_by)
SELECT '20000000-0000-4000-8000-000000000001',
       (SELECT id FROM users WHERE email = 'smilinghearts@ngo.example'),
       'owner', (SELECT id FROM users WHERE email = 'admin@idrm.local')
WHERE NOT EXISTS (
    SELECT 1 FROM organization_members
    WHERE organization_id = '20000000-0000-4000-8000-000000000001');

-- ---------------------------------------------------------------------------
-- VOLUNTEER ENROLLMENTS
-- ---------------------------------------------------------------------------
INSERT INTO volunteer_enrollments (
    user_id, scope_type, scope_id, status, self_enrolled_at, approved_by, approved_at
)
SELECT
    (SELECT id FROM users WHERE email = 'volunteer.ravi@example.com'),
    'organization', '20000000-0000-4000-8000-000000000001',
    'active', now() - INTERVAL '10 days',
    (SELECT id FROM users WHERE email = 'smilinghearts@ngo.example'),
    now() - INTERVAL '9 days'
WHERE NOT EXISTS (
    SELECT 1 FROM volunteer_enrollments
    WHERE user_id = (SELECT id FROM users WHERE email = 'volunteer.ravi@example.com'));

INSERT INTO volunteer_enrollments (user_id, scope_type, scope_id, status, self_enrolled_at)
SELECT
    (SELECT id FROM users WHERE email = 'volunteer.fatima@example.com'),
    'organization', '20000000-0000-4000-8000-000000000001',
    'pending', now() - INTERVAL '2 days'
WHERE NOT EXISTS (
    SELECT 1 FROM volunteer_enrollments
    WHERE user_id = (SELECT id FROM users WHERE email = 'volunteer.fatima@example.com'));

-- ---------------------------------------------------------------------------
-- UNITS + PERSONNEL STATUSES
-- ---------------------------------------------------------------------------
INSERT INTO units (id, organization_id, name, kind, callsign, capacity)
SELECT '21000000-0000-4000-8000-000000000001',
       '20000000-0000-4000-8000-000000000001',
       'Food Truck 01', 'vehicle', 'FT-01', 4
WHERE NOT EXISTS (SELECT 1 FROM units WHERE id = '21000000-0000-4000-8000-000000000001');

INSERT INTO unit_statuses (unit_id, status)
SELECT '21000000-0000-4000-8000-000000000001', 'in_quarters'
WHERE NOT EXISTS (SELECT 1 FROM unit_statuses WHERE unit_id = '21000000-0000-4000-8000-000000000001');

INSERT INTO units (id, organization_id, name, kind, callsign, capacity)
SELECT '21000000-0000-4000-8000-000000000002',
       '20000000-0000-4000-8000-000000000002',
       'Ambulance 07', 'ambulance', 'AMB-07', 3
WHERE NOT EXISTS (SELECT 1 FROM units WHERE id = '21000000-0000-4000-8000-000000000002');

INSERT INTO unit_statuses (unit_id, status)
SELECT '21000000-0000-4000-8000-000000000002', 'in_quarters'
WHERE NOT EXISTS (SELECT 1 FROM unit_statuses WHERE unit_id = '21000000-0000-4000-8000-000000000002');

INSERT INTO personnel_statuses (user_id, status, staffing_level)
SELECT (SELECT id FROM users WHERE email = 'volunteer.ravi@example.com'), 'available', 1
WHERE NOT EXISTS (
    SELECT 1 FROM personnel_statuses
    WHERE user_id = (SELECT id FROM users WHERE email = 'volunteer.ravi@example.com'));

INSERT INTO personnel_statuses (user_id, status, staffing_level)
SELECT (SELECT id FROM users WHERE email = 'apmedical@org.example'), 'responding', 1
WHERE NOT EXISTS (
    SELECT 1 FROM personnel_statuses
    WHERE user_id = (SELECT id FROM users WHERE email = 'apmedical@org.example'));

-- ---------------------------------------------------------------------------
-- INCIDENTS
-- ---------------------------------------------------------------------------
INSERT INTO incidents (service_type, priority, status, description, location,
                       region_id, requester_id, auto_approved, created_at)
SELECT 'water', 'medium', 'approved',
       'Water supply has been cut for 3 days in the Amberpet colony. Approximately 60 families need drinking water.',
       ST_GeomFromText('POINT(78.51 17.40)', 4326),
       (SELECT id FROM regions WHERE code = 'IN-TG-HYD'),
       (SELECT id FROM users WHERE email = 'priya.citizen@example.com'),
       TRUE, now() - INTERVAL '2 hours'
WHERE NOT EXISTS (
    SELECT 1 FROM incidents
    WHERE description LIKE 'Water supply has been cut for 3 days%');

INSERT INTO incidents (service_type, priority, status, description, location,
                       region_id, requester_id, auto_approved, created_at)
SELECT 'food', 'low', 'approved',
       'Need food packets for 25 people at a temporary shelter. Expected to last for two days.',
       ST_GeomFromText('POINT(78.49 17.37)', 4326),
       (SELECT id FROM regions WHERE code = 'IN-TG-HYD'),
       (SELECT id FROM users WHERE email = 'mohan.citizen@example.com'),
       TRUE, now() - INTERVAL '4 hours'
WHERE NOT EXISTS (
    SELECT 1 FROM incidents WHERE description LIKE 'Need food packets for 25 people%');

INSERT INTO incidents (service_type, priority, status, description, location,
                       region_id, requester_id, created_at)
SELECT 'medical', 'critical', 'created',
       'Elderly woman with chest pain. Ambulance needed urgently at the relief camp.',
       ST_GeomFromText('POINT(78.53 17.42)', 4326),
       (SELECT id FROM regions WHERE code = 'IN-TG-HYD'),
       (SELECT id FROM users WHERE email = 'sneha.citizen@example.com'),
       now() - INTERVAL '20 minutes'
WHERE NOT EXISTS (
    SELECT 1 FROM incidents WHERE description LIKE 'Elderly woman with chest pain%');

INSERT INTO incidents (service_type, priority, status, description, location,
                       region_id, requester_id, assigned_organization_id,
                       approved_by, created_at)
SELECT 'rescue', 'high', 'accepted',
       'Flood waters reached first floor. Family of 5 including 2 children trapped.',
       ST_GeomFromText('POINT(80.66 16.52)', 4326),
       (SELECT id FROM regions WHERE code = 'IN-AP-VJA'),
       (SELECT id FROM users WHERE email = 'mohan.citizen@example.com'),
       '20000000-0000-4000-8000-000000000002',
       (SELECT id FROM users WHERE email = 'coord.vja@idrm.local'),
       now() - INTERVAL '6 hours'
WHERE NOT EXISTS (
    SELECT 1 FROM incidents WHERE description LIKE 'Flood waters reached first floor%');

-- ---------------------------------------------------------------------------
-- INCIDENT UPDATES  (the timeline)
-- ---------------------------------------------------------------------------
INSERT INTO incident_updates (incident_id, from_status, to_status, actor_id, note)
SELECT i.id, NULL, 'created',
       (SELECT id FROM users WHERE email = 'priya.citizen@example.com'),
       'Request created.'
FROM incidents i
WHERE i.description LIKE 'Water supply has been cut for 3 days%'
  AND NOT EXISTS (
    SELECT 1 FROM incident_updates iu WHERE iu.incident_id = i.id);

INSERT INTO incident_updates (incident_id, from_status, to_status, actor_id, note)
SELECT i.id, 'created', 'approved', NULL,
       'Auto-approved by policy IN-TG-HYD-FOOD-WATER-LOW'
FROM incidents i
WHERE i.description LIKE 'Water supply has been cut for 3 days%'
  AND NOT EXISTS (
    SELECT 1 FROM incident_updates iu
    WHERE iu.incident_id = i.id AND iu.to_status = 'approved');

COMMIT;
