# Changelog

All notable changes to IDRM are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

Outcome of the 2026-11 code and documentation review
(`docs/review/DISCREPANCY-REGISTER.md`).

### Security

- **Help requests are no longer shown to every provider** (ADR-0015; Part G
  G-1, G-2 and gap WF3). A provider must belong to an organization a
  coordinator has verified to see or claim any request; they see approved
  requests only coarsely (location snapped to ~1 km, no description) and
  their own organization's requests in full; never the requester's account
  id or requests awaiting approval. The guest tracking token is returned only
  when the request is created. Rules: `shared/privacy.py`. Written and
  unit-checked; the API tests (`tests/api/test_incident_privacy.py`) have
  not been run against a database yet.
- **Personal data is kept out of the audit log** (ADR-0015; Part G G-6 and
  gap WF1). Audit rows can never be erased, so every audit write now masks
  personal keys (`email`, `phone`, `description`, `entity_value`, …) as
  `"[redacted]"` (`shared.privacy.redact_audit_values`). Registration, failed
  console sign-ins and blocklist additions no longer record the email or the
  blocked value. Older rows are unchanged. Hand-checked; not yet run in the app.
- **Privacy and retention settings with safe defaults** (ADR-0015). New
  `.env` settings, explained in `docs/design/DATA-CONFIGURATION.md`:
  `PRIVACY_COARSE_GRID_DEGREES` (0.01), `PRIVACY_ASSIGNEE_GRACE_HOURS` (72 —
  the assigned organization drops to the coarse view 72 h after a request
  closes), `FILE_LINK_TTL_SECONDS` (300 — was a fixed 3600),
  `AUDIT_REDACT_EXTRA_KEYS`, plus reserved rural-grid, k-anonymity,
  reveal-limit and `RETENTION_*` settings for tasks not yet built.
  Out-of-range or contradictory values stop start-up. Coarse incident
  responses now say `"location_precision": "approx"` with
  `location_grid_km` (was `"approx_1km"`). Hand-checked; not yet run.
- **Providers can read what is needed before accepting** (ADR-0015, G-5).
  Incident responses gain `summary`: the description with phone numbers,
  emails and links replaced by `[number]`, `[email]`, `[link]`, at most
  `PRIVACY_SUMMARY_MAX_CHARS` (140). Coarse views show it instead of nothing.
  The scrubber misses names, addresses and numbers in Indian-language words;
  those cases are documented and tested. Hand-checked; not yet run.
- **Photos lose their hidden location data on upload** (ADR-0015, G-3).
  Before a JPEG, PNG or WebP is stored, its metadata — GPS position, time,
  phone make and serial, comments, XMP — is removed by keeping only the
  picture and colour blocks (`shared/image_metadata.py`, standard library;
  no new dependency). A JPEG keeps only its "rotate" flag so it still shows
  the right way up; pixels are copied unchanged. A file whose bytes do not
  match its declared type is refused with 422 `invalid_image`. Resizing and
  re-encoding still need an image library; PDFs are stored as received.
  Hand-checked, including a real JPEG and PNG made by Windows; not yet run
  in the app.
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

- **The documentation tree is checked** (H-7). Each of the 30 leaf documents
  starts with `Scope / Owner of / See also`, and `scripts/lint_docs.py` (in
  `make lint` and CI) fails when `CLAUDE.md` or an index file grows past its
  size limit, a leaf cannot be reached from an index, a header is missing,
  or a relative link points at a file that does not exist.
- **Copied tables are checked against the code** (H-7 step 5).
  `scripts/lint_facts.py` (in `make lint` and CI) fails when any markdown
  table of incident transitions or of token lifetimes stops matching
  `shared/lifecycle.py` or the `shared/config.py` defaults. Other repeated
  facts were checked by hand and either kept (commands and quick-start lines
  need the value) or replaced by a link.
- **Setting names are checked** (H-7 step 5). The same script fails when a
  setting has no line in `.env.example`, `.env.example` names something that
  is not a setting (it would be silently ignored), or a document names a
  setting that does not exist. `.env.example` gains `FILE_MAX_BYTES`,
  `IMAGE_MAX_DIMENSION` and the three `AUTO_APPROVAL_*_CACHE_TTL` settings,
  the last four marked "declared, not read yet" (G-3, H-12).
- **The console overview leads with the triage queue** (ADR-0016). The first
  card, "Open Incidents" (four states, but linked to `created` only), is now
  "Waiting for Approval": it counts requests in `created` and their critical
  ones, exactly what its link opens. Written, not yet run.
- **Line endings are LF everywhere**: `.gitattributes` moved from `docs/`
  (where it protected only the documentation) to the repository root, so
  shell scripts, the Makefile and Python files are checked out with LF on
  Windows too. No stored file changed. Existing Windows checkouts: run
  `git rm -r --cached -q . && git reset -q --hard` once on a clean tree.
- **The import-boundary check covers all three rules**: `app` and
  `dashboard` may not import each other, and `shared` may not import either,
  nor FastAPI/Starlette or Flask/`flask_*`. `scripts/lint_boundaries.py`
  parses each file instead of searching text, and `make lint` now runs it
  (it used to run a separate one-line search for `from app` only).
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

- The lifecycle table in `docs/QUICK_REFERENCE.md` was missing the `assign`
  action and `docs/DIAGRAMS.md` showed it only from `approved`; both now match
  `shared/lifecycle.py` (no endpoint performs `assign` yet — H-11).
- `sql/02_tables.sql` listed table-group counts that added up to 54 (the
  schema has 60); it now points at `docs/03-data-model.md`.
- `docs/05-dashboard-guide.md` now states the console sign-in URL it owns.
- The tutorial now says the console overview has five KPI cards (it said
  four) and four lists of counts (it said "several charts"); the dashboard
  guide names each card's link.
- `docs/MANIFEST.md` lists every tracked file (272, was 227) with correct
  folder counts, drops five entries for files that do not exist, and checks
  completeness with `git ls-files | wc -l`.
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
