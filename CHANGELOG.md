# Changelog

All notable changes to IDRM are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

Outcome of the 2026-11 code and documentation review
(`docs/review/DISCREPANCY-REGISTER.md`).

### Security

- Sign-up accepts only the `citizen` and `provider` roles
- The first admin password comes from `ADMIN_INITIAL_PASSWORD`; required in production
- Both apps refuse to start in production on development defaults
- Failed-login lockout and refresh-token reuse detection now persist
- A password change ends every session
- Ownership checks on incidents, files, chat, dispatch, inventory and units
- Rate limiting per real client address (`TRUST_FORWARDED_FOR`) and per email
- A full auto-approval cap can no longer end in an approval
- `/health` returns 503 when the database is down and no error text
- Security headers on the API

### Changed

- **Approval comes first** (ADR-0014): a provider can claim only an approved
  request; a coordinator can switch auto-approval on for named regions and a
  fixed period
- Files moved to `/api/v1/files`, the audit list to `/api/v1/audit-logs`
- Policies using conditions the engine cannot evaluate no longer match
- Unknown filter values are rejected (API) or ignored (console)
- Tests run against a separate `idrm_test` database
- The demo seed refuses to run in production; `make seed-reference` loads regions only
- Removed the unused `*_VOLUNTEER_*` settings (there is no volunteer role)

### Fixed

- `make install`, `make db-create`, the CI workflow, console start-up and login, the seed
- `/incidents/nearby` was unreachable and measured in degrees
- Incident responses always had null coordinates
- The read-through cache never cached
- Queues listed low priority first
- Releasing an assignment left the unit dispatched
- `updated_at` was never maintained on seven tables (migration `0004`)

### Added

- `shared/lifecycle.py`, `shared/geo.py`, `app/core/authz.py`
- `X-Request-ID` on every response; request id and client address in logs and audit rows
- ADR-0014 and `docs/adr/ERRATA.md`

---

## [0.1.0] — 2026-10-12

The initial MVP. Two apps, one database, shared Python.

### Added

**Public API (FastAPI)**
- 13 modules: users, incidents, dispatch, personnel, organizations,
  scheduling, logistics, ICS, comms, policies, files, audit, administration
- Two-token JWT with RS256, per-role TTLs, and jitter
- Server-side session verification on every request
- Refresh-token rotation with family-based reuse detection
- Concurrent-session limits, enforced at login
- Password change and forced logout via `token_version`
- Guest incident creation with tracking tokens
- Proximity search via PostGIS `ST_DWithin`
- File uploads to MinIO with presigned downloads
- Auto-approval engine with policy-driven caps
- Entity lists: blocklist, allowlist, watchlist with hard/soft/observe effects

**Staff Console (Flask)**
- 15 blueprints: auth, main, dispatch, bigboard, incidents, personnel,
  organizations, users, scheduling, logistics, ICS, policies, alerts,
  audit, reports
- **Dispatch Console** — the three-panel CAD workflow
- **BigBoard** — widget-based situational awareness
- Policy on/off switch, decision log, entity-list management
- Volunteer enrollment approval
- Force-logout with token version bump
- CSV export with audit logging

**Shared code**
- 56 ORM models over 60 tables
- Framework-agnostic config, logging, security, sessions, cache, storage,
  audit, enums, rate limiting
- Unified governance engine for auto-approval and entity lists
- One Alembic migration history

**Design system**
- Slate + Emerald on two canvases (cool slate for the API, warm saffron
  for the console)
- WCAG AAA contrast on both canvases
- Identical component vocabulary across both apps

**Operations**
- One-command bootstrap
- Docker image buildable for both entrypoints
- Health endpoints, structured JSON logging
- CI runs tests with and without Redis

### Known limitations
- Email verification and password reset are not implemented (the tables
  exist; no endpoint uses them)
- Image content validation is by content-type header only
- Rate limiting is per-process without Redis
- No metrics endpoint (Prometheus)
- No background scheduler for token/session cleanup
- No audit partition strategy beyond a documented runbook

These are recorded in `docs/07-operations.md` and are candidates for the
FFP (First Field Pilot).

---

## Versioning

| Change type | Version bump |
|---|---|
| Breaking API change | Major |
| New feature, backward-compatible | Minor |
| Bug fix, backward-compatible | Patch |
| Documentation only | None (documented in commit) |

## Categories

- **Added** — new features
- **Changed** — changes to existing functionality
- **Deprecated** — soon-to-be-removed features
- **Removed** — removed features
- **Fixed** — bug fixes
- **Security** — security-relevant changes
