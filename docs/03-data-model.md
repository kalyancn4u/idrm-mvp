# Data Model

**60 tables across 5 layers.** Both apps read and write the same rows.

## Layers

### Identity (11 tables)

`users`, `user_sessions`, `password_reset_tokens`, `email_verification_tokens`,
`password_history`, `login_attempts`,
`personnel_statuses`, `personnel_status_events`, `units`, `unit_members`,
`unit_statuses`, `unit_status_events`.

### Reference (8 tables)

`regions`, `organizations`, `organization_members`, `resources`,
`shifts`, `shift_signups`, `shift_trades`, `personnel_certifications`.

### Transactional (12 tables)

`incidents`, `incident_updates`, `alerts`,
`notifications`, `notification_preferences`, `notification_deliveries`,
`messages`, `chat_channels`, `chat_messages`,
`dispatch_assignments`, `dispatch_offers`,
`calendar_events`, `event_rsvps`.

### Operations (11 tables)

`incident_commands`, `incident_lanes`, `lane_assignments`,
`run_logs`, `run_log_entries`,
`inventory_locations`, `inventory_items`, `inventory_transactions`,
`trainings`, `training_assignments`, `training_completions`.

### Governance + Evidence (9 tables)

`auto_approval_policies`, `auto_approval_decisions`,
`entity_lists`, `entity_list_matches`,
`rate_limit_events`, `mutual_aid_agreements`,
`bigboard_configs`, `bigboard_widgets`, `files`,
`audit_logs` (append-only).

## The core relationships

```
identity ─── account ─── access_grant ─── entitlement
   │                                           │
   └──── person can be a citizen / provider / coordinator / admin
   │
   └──── belongs to organizations (via organization_members)
   │
   └──── is enrolled as a volunteer (via volunteer_enrollments)
   │
   └──── has a personnel status (via personnel_statuses)
```

## The audit table

`audit_logs` has **no `updated_at`** and **no `deleted_at`**. A database
trigger raises an exception on any UPDATE or DELETE. It is genuinely
append-only.

| Column | Purpose |
|---|---|
| `actor_id` | Who (nullable — system) |
| `action` | `incident.created`, `dashboard.login`, … |
| `resource_type` | `incident`, `organization`, `user`, … |
| `resource_id` | The row's UUID |
| `old_values`, `new_values` | JSONB snapshots |
| `ip_address` | INET |
| `created_at` | Timestamptz |

## Enums (22)

Roles, statuses, priorities, service types, incident statuses, alert
severities, notification types, governance enums, personnel statuses,
unit statuses, ICS roles and lanes, dispatch offer statuses.

## Extensions

- **PostGIS** (required) — geometry
- **pgcrypto** (required) — UUIDs
- **pg_trgm** (recommended) — fuzzy search
- **unaccent** (recommended) — accent-insensitive search

