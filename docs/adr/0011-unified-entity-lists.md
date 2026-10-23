# ADR-0011 — Entity Lists Are One Unified Table

**Status:** Accepted

## Context

The platform needs blocklists, allowlists, and watchlists for many entity
types (users, emails, phones, IPs, device fingerprints, orgs). Each could
have its own table, or they could share one.

## Decision

One table: `entity_lists`. Discriminated by `entity_type` and `list_type`.

| Field | Values |
|---|---|
| `entity_type` | `user_id`, `email`, `phone`, `ip_address`, `device_fingerprint`, `organization_id`, `region_id` |
| `list_type` | `blocklist`, `allowlist`, `watchlist` |
| `effect` | `hard_block`, `soft_block`, `allow_override`, `observe` |

**Evaluation order:**

1. allowlist with `allow_override` → allow (bypass blocklist)
2. blocklist with `hard_block` → reject
3. blocklist with `soft_block` → allow but flag
4. watchlist → allow but log

Every match is recorded in `entity_list_matches` with the context.

## Consequences

- Adding a new entity type requires one enum value, not a new table.
- The dashboard has one screen for all list management.
- The `scope` JSONB column allows region- or service-scoped entries without
  a schema change.
