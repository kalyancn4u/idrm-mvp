# Changelog

All notable changes to IDRM are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Nothing yet.

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
- Policy authoring, decision log, entity-list management
- Volunteer enrollment approval
- Force-logout with token version bump
- CSV export with audit logging

**Shared code**
- 60 ORM models across 5 layers
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
- Email delivery is stubbed (verification tokens are returned in the API
  response rather than emailed)
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
