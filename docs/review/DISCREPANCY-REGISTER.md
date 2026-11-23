# IDRM MVP — Discrepancy Register

Review date: 2026-11-14. Reviewed commit: `e8cca37`.

## Fix status (updated 2026-11-14, third round)

> **Resuming this work?** What is still to do — mostly running these fixes
> against a real database for the first time — is in
> [PENDING-TASKS.md](PENDING-TASKS.md), in the order to do it.

**Fixed:** every item, D-001 to D-114, except the parts of D-069 listed below.
The first two rounds are in commit `2273149`; the third round (D-052 onward)
is in the working tree, not yet committed.

**Fourth round (2026-11-14) — the last nine, in the working tree:**

| ID | What was done |
|---|---|
| D-044 | Redis calls made from async code now run on a worker thread (`asafe_call`, `ainvalidate`, `allow_async`), so a slow Redis no longer stalls every request |
| D-070 | Dispatch rules live once in `shared/services/dispatch_core.py`; the async (API) and sync (console) services only load and save. The console now honours offer expiry too |
| D-071 | Every console route is guarded by a named permission; the CSV export uses `export.data` |
| D-072 | The three orphan templates have routes and links: organization detail, response times, expiring certifications |
| D-073 | `warm_cache.py` clears and then reloads the policy cache |
| D-075 | JWT key files are cached in memory and reloaded when the file changes |
| D-076 | Passwords use the `bcrypt` library directly; `passlib` and the unused `lupa` are removed. Existing hashes still verify |
| D-078 | ICS bodies no longer require `incident_id`; if sent it must match the URL. A lane must belong to the incident |
| D-069 | **Partly.** Built: in-app notifications to the requester on each state change and to a person when dispatched; password history (no reuse of the last five). **Not built, on purpose:** password reset and email verification (both need email delivery, which does not exist), `user_delegations` (needs a rule for who grants them), `notification_deliveries` / `notification_preferences` and `rate_limit_events` (no consumer). Their tables and models stay for when those features are specified |

Checked with 33 more no-database checks (108 in total, all passing), the
test suite (55 pass, 9 skipped) and `ruff` (clean). **Not run against
PostgreSQL:** notification and password-history rows being written, and
everything listed as not run in the earlier rounds.

**Fixed with a caveat:**

- D-085 — the limits of audit immutability are now documented
  (`docs/08`, `docs/adr/ERRATA.md`); no `TRUNCATE` guard was added because
  ADR-0002 keeps it on purpose.
- D-098 — `MANIFEST.md` file counts are corrected; its per-file tables were
  not rewritten and do not list the files added by these fixes.
- D-100 to D-104 — accepted ADRs are not edited; the differences are in
  `docs/adr/ERRATA.md`.
- D-105 — the seed now creates what `SEED_REFERENCE.md` lists (four
  policies, two list entries, both enrollments, the hospital type).
- D-114 — the reset instructions are fixed; the "four vs five KPI cards"
  wording was not checked against the template.

**Third round, how it was checked:** the 75 no-database behaviour checks and
the test suite (55 pass, 9 skipped) still pass; `ruff` reports no findings on
the configured rules; both YAML files parse; the doc link check finds no
broken link. **Not run:** anything needing PostgreSQL — the seed (including
its new policy, list and enrollment rows), `make test-db`, migration `0004`,
the nine database tests — and nothing was built or started in Docker.

Third-round changes that callers will notice:

- Tests marked `pg` run only on a database whose name ends in `_test`;
  `make test` points at `idrm_test`, created by `make test-db`. CI uses it too.
- `make seed` refuses to run with `APP_ENV=production`;
  `make seed-reference` loads the regions only.
- The production compose example mounts `./keys` into the API container.
- `scripts/generate_keys.py` keeps existing keys unless `--force`.
- `alembic revision --autogenerate` no longer proposes dropping tables that
  have no model.
- The API sends `X-Frame-Options`, `X-Content-Type-Options`,
  `Referrer-Policy` and `Permissions-Policy`.
- The unused `*_VOLUNTEER_*` settings are removed.
- Coverage floor is one number (60) in both the Makefile and CI.
- Imports are sorted with the project packages declared first-party in
  `pyproject.toml`.

**D-035 decided and fixed (2026-11-14).** The owner's answer: *"For some time
of disaster events, in a specific geo region and for a stipulated amount of
time — auto-approval can be set by the co-ordinator. If not set, then, the
default is, require approval."* A provider can now claim only an `approved`
request, and a coordinator can create an incident policy limited to named
regions and an end time. Recorded in
[ADR-0014](../adr/0014-approval-first.md), which also lists what is not built
(no event record, no maximum period, no coordinator-to-region link, no
console form). D-110 (picture vs table) is resolved by the same change.

Second round (D-028, D-030 to D-050), how it was checked: 34 more behaviour
checks without a database, all passing, plus the repaired test suite — 55
pass, 9 are skipped with the reason "needs PostgreSQL + PostGIS". Those nine,
and migration `0004_touch_triggers`, have **not been run**. One of them now
asserts that a low-priority food request in Hyderabad is auto-approved; that
depends on the seed and has never been observed passing.

Changes from the second round that callers will notice:

- Incident responses now carry real `latitude` / `longitude` (they were
  always `null`). No new dependency: `shared/geo.py` decodes the point.
- New incidents record their `region_id`.
- The policy/region/entity-list cache now actually caches. Creating or
  toggling a policy, or adding a list entry, clears the relevant entries.
- A policy that sets a condition the engine cannot evaluate
  (`time_of_day_*`, `min_region_verified_providers`, `max_org_type_risk`,
  `requires_documents`, `min/max_service_radius_km`, or any unknown key) no
  longer auto-approves anything, and `POST /policies` rejects it with 422.
  `max_priority` is now enforced; `max_per_requester_per_day` is enforced as
  a daily cap.
- Filters such as `?status=` are checked: an unknown value is a 422 on the
  API and is ignored on the console.
- Queues are sorted most urgent first.
- Releasing an assignment returns the unit to `in_quarters` and the person
  to `available`.
- Every response carries `X-Request-ID`; logs and audit rows now have the
  request id and client address.
- Registering an email that belongs to a deleted account returns 409.
- `sql/06_sample_data.sql` carries a hash that really is `IDRMseed#2026`.
- The console login URL is corrected to `/dashboard/auth/login` in the
  README, eight docs, three scripts and the tests.

How each group was checked:

| Items | Check | Result |
|---|---|---|
| D-001 | Workflow parsed as YAML | Valid; three jobs. Not run on GitHub. It will be red until the lint debt (D-068) and broken tests (D-047 to D-050) are fixed |
| D-002, D-003 | `make -n` dry run | Commands expand correctly. Not run against a database |
| D-004, D-005, D-006 | Started the console in a throwaway virtualenv | Login page 200, anonymous redirect 302, `login_user` works, suspended user refused |
| D-007, D-008 | Imports and compiles | **Not run** — no database on the review machine |
| D-009 to D-027, D-029 | 28 behaviour checks without a database | 28 pass. The paths that need Postgres (lockout rows surviving, refresh reuse, ownership checks, `ST_DWithin` in metres, row locks) are **not run** |
| Existing test suite | `pytest` without a database | 44 pass, 11 fail. Nine need a database; two are the known test defects D-047 and D-048. `test_health_public` and `test_health_without_redis` now need a database, because `/health` returns 503 without one (D-025) |

Behaviour that changed and that callers will notice:

- **Registration** accepts only `citizen` or `provider`. Coordinators and
  admins are made by an admin in the console.
- **First admin password** comes from `ADMIN_INITIAL_PASSWORD`. In production
  the migration refuses to run without it. Development still gets `Admin#2026`.
- **Production start-up** fails if `DASHBOARD_SECRET_KEY`,
  `DASHBOARD_SESSION_COOKIE_SECURE`, `S3_SECRET_KEY` or the database password
  are still development defaults.
- **Claiming a request** (`accept`) requires the provider to belong to an
  organization, and records that organization. Only its members may `start`
  or `complete`. A citizen may cancel or verify only their own request.
- **Refresh tokens:** replaying an already-used token ends the session family
  and invalidates the user's tokens. A password change ends every session.
- **Files** moved to `/api/v1/files` and the audit list to
  `/api/v1/audit-logs` (what `docs/04` already said). Both file endpoints now
  need a login.
- **`/health`** returns 503 when the database is down and no longer includes
  the error text.
- **Rate limiting** counts per client address; `X-Forwarded-For` is believed
  only when `TRUST_FORWARDED_FOR=1`. Login is also limited per email.
- **Chat, dispatch offers, assignments, inventory and unit status** now check
  that the caller belongs to the organization or unit concerned.
- **Console:** five wrong passwords lock the account for 15 minutes; a
  suspended or demoted user is signed out on their next click; approve and
  reject obey the same state rules as the API (now in `shared/lifecycle.py`).

Follow-ups these fixes create: the docs that describe the old behaviour
(D-012, D-013, D-055 to D-062, D-086) can now be reconciled against the new
code; `docs/08` and `docs/13` should mention the two new settings.

---

## How to read this

Each item has an **ID** (use it in commit messages, e.g. `fix(D-003): ...`), a
**where** (file and line), **what is wrong**, **why it matters** in plain
words, and **the fix**. Work top to bottom: severity **S1** stops the product
from starting or is a security hole, **S2** is a wrong result, **S3** is a
mismatch between documents and code, **S4** is tidiness.

**How this was checked.** All Python, SQL, config, scripts and tests were read.
The code was byte-compiled and linted with ruff. Nothing was *run* against a
database (this machine has no Postgres, Redis or the DB drivers), so every item
is from reading the code, not from a failing run. Items marked *(tool)* were
reported by ruff or a script.

**Coverage.** Every markdown file was compared with the code. Guides `01`–`13`,
the ADRs, `QUICK_REFERENCE`, `SEED_REFERENCE`, `DEPLOYMENT_CHECKLIST`,
`SECURITY_VERIFICATION`, `CONTRIBUTING` and `CHANGELOG` were read in full.
`CLIENT_EXAMPLES`, `TUTORIAL`, `DEMO_SCRIPT`, `DIAGRAMS` and `MANIFEST` were
checked by pulling out their URLs, commands and counts, not read sentence by
sentence. The HTML templates were checked for routes, CSRF tokens and inline
script only; their visible wording, and the colour-contrast figures in
`docs/06`, were not verified. Items D-079 onward come from this second pass.

---

## S1 — Product cannot start, or security hole

### A. Things that stop setup or startup

| ID | Where | What is wrong | Why it matters | Fix |
|---|---|---|---|---|
| D-001 | `.github/workflows/ci.yml` (whole file) | Every `:`, `/` and quote has been stripped (`name CI`, `uses actionscheckout@v4`, `ports [54325432]`). | YAML needs colons to mean "key: value". Without them GitHub cannot parse the file, so no check ever runs on a push. | Rewrite the file as valid YAML. |
| D-002 | `Makefile:48` | Uses `$(PYTHON)`, which is never defined. | The line becomes ` -m venv .venv`, which is not a command. `make venv`, `make install`, `make setup` and `scripts/bootstrap.sh` all fail on a fresh clone. | Add `PYTHON ?= python3` near the top. |
| D-003 | `Makefile:31,70-74` + `docker-compose.yml:7` | `db-create` connects as user `postgres`, but the container is created with `POSTGRES_USER: idrm_user`, so no `postgres` user exists. | First-time database creation fails; bootstrap stops there. | Connect as `idrm_user` (it is already the superuser and the DB already exists), or drop `db-create` when using compose. |
| D-004 | `dashboard/__init__.py:49` + `dashboard/extensions.py:23-42` | Calls `db.init_app(app)`, but `db` is a `_DbProxy` with no such method. `init_app` is a separate module-level function. | `create_dashboard()` raises `AttributeError`. The staff console never starts, and every dashboard test fails at the fixture. The session-cleanup hook is also never registered. | Call `extensions.init_app(app)` (or add the method to `_DbProxy`). |
| D-005 | `shared/models/identity.py:21` + `dashboard/blueprints/auth.py:51` | `User` does not provide what Flask-Login needs (`get_id`, `is_authenticated`, `is_anonymous`). | `login_user(user)` calls `user.get_id()` and crashes, so nobody can sign in to the console. | Add `flask_login.UserMixin` behaviour via a small wrapper class in `dashboard/` (keep Flask out of `shared/`). |
| D-006 | `dashboard/services/dispatch.py:130` *(tool: F821)* | `UnitStatusEvent` is used but never imported. | Assigning a unit from the Dispatch Console raises `NameError`. | Add it to the import on line 19. |
| D-007 | `scripts/seed.py:28,88` + `alembic/versions/0003_seed_admin.py:19` | The migration inserts `admin@idrm.local` with id `0000…0001`; the seed looks for id `1000…0001`, does not find it, and inserts the same email again. | `users.email` is unique, so `make seed` crashes on its first user. | Look the user up by email, not id. |
| D-008 | `scripts/seed.py:112-115`; nothing applies `sql/05_regions_and_policies.sql` | Seed stops with "No regions found — run `make migrate` first", but migrations never create regions. Only `sql/05` does, and no Makefile target, script or migration runs it. | Organizations, incidents and policies are never seeded, and auto-approval can never match a region. The message sends the reader to the wrong fix. | Create regions in the seed script or a data migration; fix the message. |

### B. Security holes

| ID | Where | What is wrong | Why it matters | Fix |
|---|---|---|---|---|
| D-009 | `app/modules/users/router.py:44,96` | Registration accepts `role` from the caller. | Anyone can send `"role":"admin"` and become an administrator. | Remove `role` from `RegisterRequest`; always create `citizen` (provider by a separate approved flow). |
| D-010 | `alembic/versions/0003_seed_admin.py:21` | A fixed admin password (`Admin#2026`) is inserted by a migration, and is printed in README and scripts. | Migrations run in production too, so every deployment gets a publicly known admin login. | Read the password from an env var, refuse to run without it in production, force a change on first login. |
| D-011 | `app/core/dependencies.py:34-41` + `users/router.py:117-134,195-204` | The DB session rolls back whenever an error is raised. Login failure and refresh-reuse both write rows and then raise. | The failed-attempt counter, the 15-minute lock, the `login_attempts` rows, the family revocation and the token-version bump are all undone. Brute-force protection and theft detection do nothing. | Commit those writes in their own transaction before raising. |
| D-012 | `users/router.py:268-277`, `177-230` | Password change bumps `token_version` but does not revoke sessions, and `/auth/refresh` never checks token version. | A thief holding a refresh token can still mint fresh access tokens after the victim changes password. `docs/13` line 80 says all sessions are revoked. | Revoke all sessions on password change (`revoke_all_for_user` exists, unused) and compare versions in refresh. |
| D-013 | `users/router.py:209-211` | Replaying an already-rotated refresh token only returns "does not match". | `docs/13` lines 60-67 promise that a reused token revokes the whole family. It does not; that branch only fires if the session was already revoked. | Treat a hash mismatch on a live session as reuse. |
| D-014 | `incidents/router.py:267-315` | State changes check only the role, not ownership. `accept` never sets `assigned_organization_id`. | Any citizen can cancel anyone's request; any provider can start or complete a request another provider claimed; two providers can claim the same one. | Check requester for cancel, set and check the assigned organization, lock the row (`SELECT … FOR UPDATE`). |
| D-015 | `users/router.py:302-304` | `DELETE /users/me/sessions/{id}` revokes any session id without checking it belongs to the caller. | Called an IDOR: acting on someone else's object by knowing its id. | Add `user_id == caller` to the query. |
| D-016 | `incidents/router.py:250-264` | Any signed-in user can read the timeline of any incident. | Leaks other people's requests. | Reuse the access rule from `get_incident`. |
| D-017 | `files/router.py:30-71` | Upload needs no login; download needs no login; `purpose` and file extension are unchecked; the file goes to MinIO before the DB row is validated. | Anyone can fill storage or fetch any file by id; a bad `purpose` gives a 500 and leaves an orphan object. `docs/04` says both need a user. | Require auth, validate `purpose` as `FilePurpose`, sanitize the extension, check access on download. |
| D-018 | `comms/router.py:55-108`, `dispatch/router.py:73-90`, `logistics/router.py:103-122`, `personnel/router.py:128-138` | No membership or organization checks. | Any user can read or post in any chat channel, answer any dispatch offer, release any assignment, change any organization's stock or any unit's status. | Add ownership checks per endpoint. |
| D-019 | `shared/rate_limit.py:110-113`, `app/core/dependencies.py:90-94` | The limiter keys on the last 32 characters of the `Authorization` header, else on `X-Forwarded-For`. | Both are chosen by the caller, so sending a random header each time bypasses the login limit. | Key on the real peer address (trusted proxy only), and on the email for login. |
| D-020 | `shared/governance/counters.py:21-35,84-96` | When a cap is exceeded the Lua script returns an error; the code treats any error as "Redis is down" and falls back to Postgres, which skips per-requester, per-provider and per-service caps. | An exceeded cap can still end in an approval. `docs/12` says a cap miss moves to the next policy. | Return a distinct "exceeded" result from Lua and stop there. |
| D-021 | `shared/sessions.py:112-131,183-204` | On the cached path the session object is rebuilt with `last_activity_at = now`; `revoke_family` and `revoke_all_for_user` do not clear the cache. | The idle timeout never fires while Redis is up, and a revoked session can keep working for up to 60 seconds. README says revocation is immediate. | Cache `last_activity_at`; invalidate cache on every revoke. |
| D-022 | `dashboard/services/incidents.py:62-88` | Approve and reject set the status with no state check. | A coordinator can "approve" a verified or cancelled request. The state machine lives in `app/`, which the dashboard may not import. | Move `lifecycle.py` to `shared/` and use it in both apps. |
| D-023 | `dashboard/blueprints/auth.py:20-62`, `dashboard/extensions.py:54-63` | Console login has no lockout or rate limit, and a suspended or demoted user stays signed in. | Password guessing is unlimited; removing access does not take effect. | Apply lockout; re-check status and role in `load_user`. |
| D-024 | `shared/config.py:96`, `dashboard/__init__.py:33` | Default `SECRET_KEY` is `change-me-dashboard` with no production check (`is_production` is never used). | Anyone who knows the default can forge console session cookies. | Fail startup in production if the default is still set. |
| D-025 | `administration/router.py:24-33` | `/health` returns the raw database error text, and always HTTP 200. | Error text can expose host names; the Docker healthcheck can never report unhealthy. | Return a generic message and 503 when degraded. |

---

## S2 — Wrong result

| ID | Where | What is wrong | Why it matters | Fix |
|---|---|---|---|---|
| D-026 | `incidents/router.py:234,363` | `/incidents/nearby` is declared after `/incidents/{incident_id}`. | FastAPI matches routes in order, so "nearby" is read as an id and rejected with 422. The provider's main feature is unreachable. | Declare `nearby` before the `{incident_id}` route. |
| D-027 | `incidents/router.py:376-380` | `ST_DWithin` is given metres but the column is a geometry in degrees. | 10 km becomes 10 000 degrees, so every incident on Earth matches. | Cast both sides to `geography`. |
| D-028 | `incidents/router.py:60-68` + `requirements.txt` | `to_shape` needs the `shapely` package, which is not listed; the import error is swallowed. | Every incident response has `latitude` and `longitude` as `null`. | Add `shapely`, or select `ST_Y`/`ST_X` in SQL. |
| D-029 | `app/main.py:93-94`, `files/router.py:30`, `audit/router.py:22` | The files and audit routers are mounted at `/api/v1` with route path `""`. | Upload is `POST /api/v1`, audit is `GET /api/v1`, download is `/api/v1/{id}/download`. `docs/04` says `/files` and `/audit-logs`. | Mount with `prefix="/api/v1/files"` and `"/api/v1/audit-logs"`. |
| D-030 | `shared/cache.py:87` and its three users | Keys use named placeholders (`{applies_to}`) but callers pass positional arguments. | `format` raises `KeyError`, which is caught, so the cache is silently skipped every time. Policy, region and entity-list caching never happens. | Bind arguments by name with `inspect.signature`. |
| D-031 | `incidents/router.py:114-123` | `region_id` is never set on a new incident. | Region reports and any region scoping cannot work for API-created requests. | Store the region found by the evaluator. |
| D-032 | `incidents/router.py:144`, `evaluator.py:156-163`, `schema.py:13-31` | Trust score is hard-coded to 0, and only two of twelve declared policy conditions are evaluated. | A policy author who sets `time_of_day_start` or `max_per_requester_per_day` believes it is enforced. It is ignored, so more is auto-approved than intended. | Implement each condition or reject unknown ones. |
| D-033 | `evaluator.py:147` | A region-scoped policy matches when no region was found. | Provider subjects skip the region rule entirely. | Return `False` when the policy has a scope and region is `None`. |
| D-034 | `policies/router.py:47-61`, `123-139` | Policies are saved without `validate_policy`, and neither policies nor list entries write an audit row. | Bad policies are stored then silently skipped; governance changes leave no trace. | Validate and call `log_async`. |
| D-035 | `lifecycle.py:12` vs `README.md:120-130` | `accept` is allowed straight from `created`. | A provider can skip coordinator approval. README shows approval first. | Decide which is intended, then align code, tests and README. |
| D-036 | `dispatch/router.py:108`, `dashboard/services/bigboard.py:37` | `ORDER BY priority ASC` on an enum declared `low, medium, high, critical`. | Low-priority requests are listed first. | Order descending. |
| D-037 | `shared/services/dispatch.py:136-151` | Releasing an assignment does not reset unit or person status. | Units stay "dispatched" forever. | Set status back on release. |
| D-038 | `scheduling/router.py:154-160` | `a.id` is read before the row is flushed. | The response is a list of the text `"None"`. | Flush before collecting ids. |
| D-039 | `0002_resgrid.py` vs `sql/04_triggers.sql:35-41` | Seven tables listed for the `updated_at` trigger never get it in a migration. | `updated_at` goes stale on units, shifts, inventory and others. | Add the triggers in a new migration. |
| D-040 | `sql/06_sample_data.sql:11,24` | The comment says the hash is for `IDRMseed#2026`; checked with bcrypt, it is not. | Users seeded from SQL cannot log in with the documented password. | Regenerate the hash. |
| D-041 | `users/router.py:85-88` vs unique email | Registration ignores soft-deleted users but the unique index does not. | Re-registering a deleted email gives a 500. | Use a partial unique index or check all rows. |
| D-042 | `users/router.py:318-321`, `incidents/router.py:177-182`, others | Filter values go to the database unvalidated; `int(request.args.get("page"))` in every dashboard list. | A typo such as `?status=opne` or `?page=abc` gives a 500 instead of a clear 422/400. | Type the parameters as enums and ints. |
| D-043 | `shared/logging.py:10-11` | `client_ip_ctx` and `request_id_ctx` are never set anywhere. | Every audit row has no IP; every log line has request id `-`. `docs/08` T7 claims IP on every write. | Add middleware in both apps. |
| D-044 | `shared/cache.py:26,48`, all `safe_call` uses | Redis is marked unavailable forever after one failure, and the blocking client is called from async code. | One blip disables caching until restart; a slow Redis stalls every request for up to 1 s. | Retry after a cool-down; use `redis.asyncio`. |
| D-045 | `dashboard/services/reports.py:28-42`, `kpi.py:37-45` | "Response time" measures created→verified; several counts include deleted rows. | Numbers on the console mean something other than their label. | Rename or recompute; add `deleted_at IS NULL`. |
| D-046 | `dashboard/templates/base.html:56` vs CSP in `dashboard/__init__.py:103` | Inline `onclick` with a policy that forbids inline script. | The flash "dismiss" button does nothing. | Move the handler to `static/js/app.js`. |

### Tests that cannot catch anything

| ID | Where | What is wrong | Fix |
|---|---|---|---|
| D-047 | `tests/dashboard/test_rbac.py:7`, `scripts/smoke.sh:27` | Expect 200 at `/dashboard/login`; the route is `/dashboard/auth/login` (the same test file relies on that two tests later). | Use the real path. |
| D-048 | `tests/api/test_dispatch.py:24-32` | Expects `OfferBody` to reject a missing unit and user; the model has no such rule. | Add a model validator. |
| D-049 | `tests/api/test_auth.py:26`, `test_incidents.py:18,49`, `integration/test_auto_approval.py` | Accept 500 as a pass, or assert only inside `if status == 201`. A test that passes when the server crashes proves nothing. | Assert one expected status; skip explicitly when there is no DB. |
| D-050 | `integration/test_no_redis.py:12`, `test_auto_approval.py:53-56` | Change env vars but settings are cached; the kill-switch test never restores the cache. | Clear `get_settings` cache in a fixture, before and after. |

---

## S3 — Documents disagree with the code

| ID | Document says | Code does |
|---|---|---|
| D-051 | `README.md:42`, `scripts/bootstrap.sh:46`, `run_all.sh:25`: console at `/dashboard/login` | `/dashboard/auth/login` |
| D-052 | `README.md:83,106`: 60 tables in `shared/models` | 60 tables in migrations, 56 models (`api_keys`, `geocode_cache`, `webhook_*` have none); `0001` docstring says 29 tables but creates 30 |
| D-053 | `README.md:96,100`: 2 migrations, 13 documents | 3 migrations, 24 documents plus 13 ADRs |
| D-054 | `sql/02_tables.sql:3`: "the complete 60-table schema" | The file is comments only. ADR-0001 is titled "SQL as source of truth" while this file calls Alembic authoritative |
| D-055 | `README.md:26`, `.env.example`, `shared/config.py`, `docs/13:44`: a `volunteer` role with its own TTLs | `UserRole` has four values, no volunteer; `/volunteers/enroll` refuses citizens |
| D-056 | `docs/08:25`: passwords use `pbkdf2:sha256:600000` | bcrypt cost 12 (the same page says so in T1). T2 "Auditor" and T11 "false_positive" describe a different product; the ISO table cites a `roles` table that does not exist |
| D-057 | `docs/04:3`: everything except `/health` needs auth | `/info`, organization list, incident create, tracking, files are open |
| D-058 | `docs/04:76-77`: `GET`/`PATCH /users/{id}` | Not implemented |
| D-059 | `docs/04`: no mention | Chat, messages, notifications, shifts, trainings, calendar, inventory, ICS, run logs, volunteer reject all exist |
| D-060 | `docs/12:57`: Redis down → deferred | Falls back to Postgres (line 13 of the same page says so) |
| D-061 | `docs/12:5,70-72`: providers auto-approved; email blocks re-registration; IP blocks a CIDR | Evaluator runs only for incidents; lists are checked only for email at incident creation; matching is exact text |
| D-062 | `docs/13:82`, `docs/08:73`: blacklist flow; create policies in the dashboard | Neither exists |
| D-063 | `shared/rate_limit.py:1-7`: Postgres fallback, every decision logged | In-process bucket only; `RateLimitEvent` is never written |
| D-064 | `shared/__init__.py:5-10`: `shared` is neutral; boundary enforced by `make lint` | `shared/rate_limit.py` imports `fastapi` and `app.core`; the rule is written three times (Makefile, `lint_boundaries.py`, CI) and none checks `shared → app` |
| D-065 | `Makefile:134` coverage floor 75 | CI floor 60 |
| D-066 | `pyproject.toml:5,9` Python 3.11 | Dockerfile and CI use 3.12 |
| D-067 | `CONTRIBUTING.md` links `docs/CONVENTIONS.md` | File does not exist *(tool)* |

---

## S4 — Tidiness

| ID | Where | What |
|---|---|---|
| D-068 | whole tree *(tool)* | ruff: 44 unused imports, 53 unsorted import blocks, 2 unused variables |
| D-069 | `shared/sessions.py:196,207`, `schema.py:46`, models `UserDelegation`, `PasswordHistory`, `PasswordResetToken`, `EmailVerificationToken`, `Notification*` | Written but never called; no password-reset or email-verification endpoint; notifications are never created so the list is always empty |
| D-070 | `dashboard/services/dispatch.py` vs `shared/services/dispatch.py` | Same logic twice (sync and async) and already drifting: only one checks offer expiry |
| D-071 | `dashboard/security.py:13-40` | `view.*` and `export.data` permissions are defined but no route checks them |
| D-072 | `dashboard/templates/organizations/detail.html`, `reports/response_times.html`, `scheduling/certifications.html` | Templates with no route |
| D-073 | `scripts/warm_cache.py` | Named "warm" but only deletes keys |
| D-074 | `scripts/generate_keys.py` | Overwrites existing keys on every run, logging everyone out |
| D-075 | `shared/security.py:40,78,115` | Reads key files from disk on every request |
| D-076 | `requirements.txt` | `passlib 1.7.4` with `bcrypt 4.1.3` logs a version warning; `lupa==2.2` is unused by the code; no final newline |
| D-077 | `Makefile:36` | Four colour variables on one line, so only the first is defined |
| D-078 | `ics/router.py:27-40` | `incident_id` required in both path and body; body value ignored |

---

## Second pass — remaining documents (D-079 onward)

### S1 — deployment and security

| ID | Where | What is wrong | Why it matters | Fix |
|---|---|---|---|---|
| D-079 | `.dockerignore:20-21`, `docker-compose.prod.yml.example:10-58`, `docs/07:14-29` | The image excludes `keys/` and `*.pem`, and neither the compose example nor the runbook mounts them. | Inside the container there is no JWT key file, so login fails when it tries to sign a token. | Mount the keys as a secret volume and document it. |
| D-080 | `docs/DEPLOYMENT_CHECKLIST.md:74-77` | The production checklist says to run `make seed`. | The seed creates demo coordinators, providers and citizens whose password is printed in the README. | Split reference data (regions, policies) from demo users; never run demo seed in production. |
| D-081 | `docs/07:20`, `docs/08:132-133`, `docs/10:86`, `QUICK_REFERENCE:225`, `DEPLOYMENT_CHECKLIST:10,41`, both compose/env examples | They tell the operator to set `SECRET_KEY` and `SESSION_COOKIE_SECURE`. | `shared/config.py` only reads `DASHBOARD_SECRET_KEY` and `DASHBOARD_SESSION_COOKIE_SECURE`, and unknown names are ignored silently (`extra="ignore"`). An operator following `docs/07` alone ships the default secret key. | Use the real names everywhere; consider `extra="forbid"` so typos fail loudly. |
| D-082 | `DEPLOYMENT_CHECKLIST:39` | "`APP_ENV=production` enables the production config guard." | No guard exists (see D-024). | Build the guard, or remove the sentence. |
| D-083 | `alembic/env.py:26`, ADR-0001 "Autogenerate is safe", `Makefile:80-82` | Four tables (`api_keys`, `geocode_cache`, `webhook_subscriptions`, `webhook_deliveries`) have no model, and PostGIS's own tables are not excluded. | `make revision` compares the database with the models, so it would generate `DROP TABLE` for those tables. | Add the missing models or an `include_object` filter. |
| D-084 | `tests/conftest.py`, `QUICK_REFERENCE:164-165` | The docs say tests use a separate `idrm_test` database. Nothing creates or selects one. | Tests write incidents into the development database (and into whatever `DATABASE_URL` points at). | Add a test database fixture with rollback. |
| D-085 | `docs/10:45-54`, ADR-0003 "anyone cannot tamper" | The troubleshooting guide shows how to drop the audit trigger; the app's own DB user owns the table, so it can. ADR-0002 also notes `TRUNCATE` still works. | "Immutable" is true only against accidental edits, not against the application account. | Run the app as a non-owner role; add a `BEFORE TRUNCATE` trigger; soften the claim. |

### S3 — documents disagree with the code

| ID | Document says | Code does |
|---|---|---|
| D-086 | `SECURITY_VERIFICATION` T6: reusing R1 returns "reuse detected", R2 is then dead, and `audit_logs.severity` is `critical` | R1 returns "does not match", R2 keeps working (D-013), and `audit_logs` has no `severity` column, so the query errors |
| D-087 | `SECURITY_VERIFICATION` T1: sample output shows the same hash prefix for two users while saying hashes are unique per user | The sample is the wrong hash from `sql/06` (D-040) |
| D-088 | `SECURITY_VERIFICATION` T9 and T12 use `/dashboard/login`; T12 says the CSP blocks inline handlers | Path is `/dashboard/auth/login`; the base template relies on an inline handler (D-046) |
| D-089 | `SECURITY_VERIFICATION` T8: "ownership is checked in the service layer" | It is checked in the route, and only for reading one incident (D-014, D-016) |
| D-090 | `DEPLOYMENT_CHECKLIST:216-228`: the API returns `X-Frame-Options`, CSP and `Permissions-Policy` | Only the dashboard sets headers; nothing sets `Permissions-Policy` |
| D-091 | `DEPLOYMENT_CHECKLIST:174-176`, `QUICK_REFERENCE:259`, `CONTRIBUTING`: logs in `logs/idrm.log`, rotated at 5 MB × 5 | Logging writes to stdout only; there is no file or rotation |
| D-092 | `DEPLOYMENT_CHECKLIST:284`: `BASE_URL=… make smoke` | `smoke.sh` reads `API_URL` and `DASH_URL`; `BASE_URL` is ignored and it tests localhost |
| D-093 | `DEPLOYMENT_CHECKLIST:142-146`, `docs/10:89-94`: enable `ProxyFix` | Not present in `dashboard/__init__.py` |
| D-094 | `docs/07:121-127`, `docs/10:33,64-77,96-104,181-183`, `docs/09:156-161`, `docs/03:44-46`, `docs/07:45,103` | Text left over from a different product: columns `username`, `is_active`, `failed_login`; table `audit_event`; hash `PLACEHOLDER`; PBKDF2; an `auditor` role; `db.create_all()`; SQLite; `fn_severity_points`; "findings" and "scans"; `identity ─ account ─ access_grant ─ entitlement`. None exist here. The SQL shown fails if pasted |
| D-095 | `docs/07:108-109`, `docs/10:59-60`: `/dashboard/decisions` | `/dashboard/policies/decisions` |
| D-096 | `docs/07:162`: raise `SQLALCHEMY_POOL_SIZE` | Pool sizes are hard-coded in `shared/db.py:29-30,57-58` |
| D-097 | `docs/03`: 60 tables, section sizes 11/8/12/11/9, 22 enums | The lists hold 12/8/13/11/10 = 54 names; `volunteer_enrollments`, `user_delegations` and the four model-less tables are missing; there are 34 enums. `MANIFEST:61` repeats "22 enums" |
| D-098 | `MANIFEST`: shared 33, app 27, dashboard 63, templates 24, scripts 7, tests 18, docs 32 files | Tracked: shared 36, app 35, dashboard 68, templates 31, scripts 8, tests 17, docs 39 |
| D-099 | `docs/02:71`, ADR-0007: the create-incident response has an `auto_approval` object | It has a single `auto_approved` true/false field |
| D-100 | ADR-0007: policies validated "on load and write"; "never fail-open, any error results in deferred" | Not validated on write (D-034); a cap error can approve (D-020); any other exception fails the whole request with 500 |
| D-101 | ADR-0002 title: "Audit capture lives in the database" | Its own decision text says the application writes the rows; only immutability is in the database |
| D-102 | ADR-0006: the dashboard's write surface is 12 routes; entity-list entry is a coordinator action | Dispatch assign, offer and release are three more write routes; entity-list creation needs `act.policies`, which only admin has |
| D-103 | ADR-0010 and ADR-0013: 60-second revocation window; README and `docs/13:51`: revocation is immediate | The documents contradict each other; the code behaves like the ADRs (D-021) |
| D-104 | ADR-0012: approval by a coordinator of the same scope, extended by `user_delegations` | Any coordinator approves anything; delegations are never read |
| D-105 | `SEED_REFERENCE`: four policies, two entity-list rows, Ravi's active enrollment, AP Medical is a hospital | `scripts/seed.py` creates one policy, no list rows, only Fatima's enrollment, and every organization as `ngo`. The rest exists only in `sql/05`–`06`, which nothing runs. The file says "keep the two in sync"; they are not |
| D-106 | `SEED_REFERENCE:126-127`: registering as `spam@bad.example` is blocked; a watched IP is observed at login | Neither registration nor login consults entity lists (D-061) |
| D-107 | `docs/05:83`: Dispatch and Offer both update personnel and unit status | Offer changes no status |
| D-108 | `docs/06:59`: the two CSS files are byte-identical except four tokens | `app/static/css` is 165 lines, `dashboard/static/css` is 644. The API serves no HTML, so its stylesheet is unused |
| D-109 | `QUICK_REFERENCE:170-172`: sample `ST_DWithin(location, …, 5000)` | Same degrees-not-metres mistake as D-027 |
| D-110 | README and `QUICK_REFERENCE` lifecycle picture vs the table directly beneath it | Picture: reject only from `created`, accept only from `approved`. Table and code: reject also from `approved`, accept also from `created` (D-035) |
| D-111 | `CHANGELOG`: 60 ORM models; policy authoring in the console; verification tokens returned by the API; CI runs tests | 56 models; console can only toggle a policy; no verification endpoint exists; CI file is unparseable (D-001) |
| D-112 | `CONTRIBUTING`: every table has `created_at`/`updated_at`; every foreign key is indexed; each module has `schemas.py`; `make lint` blocks `app → dashboard` | Many tables lack `updated_at`; most foreign keys have no index; schemas sit inside `router.py`; that direction is not checked |
| D-113 | `docs/02:79` and Dockerfile: 4 gunicorn workers; `Procfile` | `Procfile` runs the API as a single uvicorn process and the dashboard with 2 workers |
| D-114 | `TUTORIAL:327-328`: `make db-reset` then `make seed`; overview has four KPI cards | `db-reset` already seeds; `docs/05:43` says five cards |

---

## Suggested order of work

1. D-002, D-003, D-004, D-005, D-006, D-007, D-008 — make it install, start and seed.
2. D-001, D-047 to D-050 — make CI and tests able to fail.
3. D-009 to D-025 and D-079 to D-085 — close the security and deployment holes
   (D-009, D-010, D-011 first).
4. D-026 to D-046 — correct results.
5. D-051 to D-067 and D-086 to D-114 — bring documents back in line. Start
   with D-094 (delete the text from the other product) and D-081 (wrong
   setting names), then use the instruction tree in
   `INSTRUCTION-HIERARCHY.md` so each fact lives in one place.
6. D-068 to D-078 — tidiness.
