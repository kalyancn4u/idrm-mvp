# Pending Tasks — handover

Everything that is still to do, in the order to do it, written so that
someone (or an AI assistant) can pick the work up on a **new machine** with
nothing but this repository.

| | |
|---|---|
| Written | 2026-11-15 |
| Branch holding the work | `fix/review-findings-and-approval-first` (3 commits on top of `main`) |
| Last commit | `6ad05f1` — Add the server installer and the infrastructure master plan |
| State of the tree | clean |

**How to use this file.** Work top to bottom. Each task says what to do, why,
the commands, and how you know it is done. When a task is finished, change its
`[ ]` to `[x]` and add the date and one line of what happened — especially
anything that had to be fixed. That keeps this file the single place that
says where things stand.

---

## 0. The one thing to understand first

**Almost all the remaining work is "run it for real".**

The review found 114 problems; they are fixed in code (see
[DISCREPANCY-REGISTER.md](DISCREPANCY-REGISTER.md)). But the machine the fixes
were written on had no PostgreSQL, so they were checked only with tests that
need no database. Nothing below Part B has ever run against a real database,
Docker, GitHub or a real server.

So expect the first real run to turn up faults. That is normal and is the
point of Part B. Fix what you find, note it here, and carry on.

What "tested" has meant so far:

| Claim | Evidence |
|---|---|
| Code compiles and lints clean | `ruff` reports nothing on the configured rules |
| 55 tests pass | They need no database |
| 9 tests are skipped | They need PostgreSQL and have **never run** |
| 108 behaviour checks pass | Throwaway scripts, not in the repository, no database |
| Installer `detect`, `plan`, `verify` work | Run on Ubuntu 22.04 amd64 under WSL |
| Installer `apply` works | **No evidence. Never run.** |

---

## Part A — Get the work onto the new machine

### [ ] A-1. Push the branch (on the OLD machine)

The three commits exist only on the old laptop. Until they are pushed, a new
machine cannot get them.

```bash
git push -u origin fix/review-findings-and-approval-first
```

Done when: the branch is visible at `https://github.com/kalyancn4u/idrm-mvp`.
Pushing also starts the CI workflow for the first time — see B-6.

### [ ] A-2. Clone and switch to the branch (on the NEW machine)

```bash
git clone https://github.com/kalyancn4u/idrm-mvp.git
```

```bash
cd idrm-mvp
```

```bash
git checkout fix/review-findings-and-approval-first
```

Done when: `git log --oneline -1` shows `6ad05f1`.

### [ ] A-3. Read these, in this order (20 minutes)

1. `CLAUDE.md` at the repository root — the standing rules and where to look.
2. This file.
3. The "Fix status" section at the top of [DISCREPANCY-REGISTER.md](DISCREPANCY-REGISTER.md).
4. [ADR-0014](../adr/0014-approval-first.md) — the one product decision made during the review.

---

## Part B — Run it for real (do these in order)

Use an **Ubuntu** machine (22.04 or 24.04). You need Docker, `make`, Python
3.11 or newer with the venv module, and the PostgreSQL client tools:

```bash
sudo apt-get install -y make python3-venv postgresql-client
```

### [ ] B-1. Development setup from scratch

Why: proves the fixes to the Makefile, the migrations and the seed
(register items D-002, D-003, D-007, D-008).

```bash
make setup
```

That runs, in order: create the virtualenv, install packages, create `.env`,
generate JWT keys, start PostgreSQL/MinIO/Redis in Docker, create the
database, apply migrations, load the demo data.

Done when it ends with `✔ setup complete` and:

```bash
make psql
```

```sql
SELECT count(*) FROM users;                     -- expect 10
SELECT code FROM regions ORDER BY 1;            -- expect 3 rows
SELECT code, active FROM auto_approval_policies ORDER BY 1;   -- expect 4 rows
SELECT version_num FROM alembic_version;        -- expect 0004_touch_triggers
```

Most likely to fail, and where to look:

| If this fails | Look at |
|---|---|
| `make db-create` | `Makefile` — it now connects as `idrm_user`, the container's superuser |
| `make migrate` at `0003` | `alembic/versions/0003_seed_admin.py` — it now imports `shared.security` |
| `make migrate` at `0004` | `alembic/versions/0004_touch_triggers.py` — **never applied before** |
| `make seed` | `scripts/seed.py` — the policy, entity-list and enrollment rows are new |

### [ ] B-2. Start both apps and smoke-test them

Why: proves the console starts and both apps answer (D-004, D-005, D-006).

```bash
make run
```

In a second terminal:

```bash
make smoke
```

Done when smoke prints `5 passed, 0 failed`. Then, in a browser:

- `http://127.0.0.1:5000/dashboard/auth/login` — sign in as
  `admin@idrm.local` / `Admin#2026`. Open **Dispatch**, **BigBoard**,
  **Reports → Response times**, **Organizations →** click a name. Every page
  must load.
- `http://127.0.0.1:8000/docs` — the API page loads.

### [ ] B-3. Run the database tests for the first time

Why: nine tests have never executed. One asserts that a low-priority food
request in Hyderabad is auto-approved; that depends on the seed.

```bash
make test-db
```

```bash
make test
```

Done when: `64 passed` and **0 skipped**. If tests are skipped with "named
\*_test", `make test-db` did not finish.

### [ ] B-4. Lint and coverage

```bash
make lint
```

```bash
make test-cov
```

Done when both pass. The coverage floor is 60 (see decision C-5).

### [ ] B-5. Prove the security fixes by hand

Why: these behaviours only exist with a database, and are the most important
fixes in the review. Follow
[SECURITY_VERIFICATION.md](../SECURITY_VERIFICATION.md), tests T1 to T13, and
additionally check:

| Check | How | Expect |
|---|---|---|
| Nobody can self-register as staff (D-009) | `POST /api/v1/auth/register` with `"role":"admin"` | 403 |
| Lockout survives (D-011) | Six wrong passwords for one account, then `SELECT failed_login_attempts, locked_until FROM users` | `locked_until` is set; six rows in `login_attempts` |
| Reuse detection (D-013) | Test T6 in the verification doc | R1 → "reuse detected"; R2 → `session_revoked` |
| Password change ends sessions (D-012) | Change password, then refresh with the old refresh token | 401 |
| Ownership (D-014) | Citizen B cancels citizen A's request | 403 |
| Approval first (ADR-0014) | A provider calls `accept` on a `created` request | 409 `invalid_transition` |
| Coordinator policy limits (ADR-0014) | A coordinator posts a policy with no `effective_to` | 403 |
| Nearby search in metres (D-026, D-027) | `GET /api/v1/incidents/nearby?latitude=17.4&longitude=78.48&radius_km=5` as a provider | Only Hyderabad requests, with real coordinates |
| Notifications (D-069) | Approve a citizen's request, then `GET /api/v1/notifications` as that citizen | One "Request approved" row |
| Password history (D-069) | Change password, then try to change back | 422 |

Done when every row behaves as expected. Record any that do not.

### [ ] B-6. Continuous integration on GitHub

Why: the workflow file was unparseable before; it has been rewritten but
never run.

Pushing the branch (A-1) starts it. Open the **Actions** tab of the repository.

Done when the `lint`, `test` and `docker` jobs are all green. Expect to fix
something on the first run — the workflow has only ever been checked as valid
YAML.

### [ ] B-7. Build the Docker image

```bash
docker build -t idrm:0.1.0 .
```

Done when it builds. Note that `requirements.txt` no longer contains
`passlib` or `lupa`.

### [ ] B-8. First real run of the server installer

Why: `apply` has never run on any machine.

**Use a disposable machine** — a fresh cloud VM, or one with a snapshot you
can roll back to. Guide:
[INFRASTRUCTURE-MASTER-PLAN.md](../infra/INFRASTRUCTURE-MASTER-PLAN.md).

```bash
bash infra/install.sh
```

Read the plan. Then:

```bash
bash infra/install.sh apply
```

Done when all eleven acceptance checks **A1 to A11** in section 12 of the
master plan hold. The ones most worth doing: A3 (a second `apply` prints
"Nothing to do"), A5 (database ports refuse connections from another
machine), A8 (it survives a reboot).

Things that have never been verified and may need fixing:

| Item | If it is wrong |
|---|---|
| The MinIO download address | Use `--without-minio`, or set `IDRM_MINIO_URL` |
| The PostgreSQL signing-key fingerprint (22.04 only) | The step stops safely; correct the constant in `infra/idrm_infra.py` after checking the real fingerprint on postgresql.org |
| systemd hardening options | A service will not start; `sudo journalctl -u idrm-api -n 50` names the cause |
| Package names on Ubuntu 24.04 | `apt-get` reports the missing name |

### [ ] B-9. The other three installer targets

Repeat B-8 on each machine type you intend to support: Ubuntu 24.04 amd64,
24.04 arm64, 22.04 arm64. Only 22.04 amd64 has been looked at, and only
read-only.

### [ ] B-10. Production profile with a real domain

On a server with a domain name pointing at it:

```bash
bash infra/install.sh apply --profile production --domain YOUR.DOMAIN --with-firewall
```

Then HTTPS, as in section 11 of the master plan. Done when the console login
works over `https://` and acceptance check A11 holds.

---

## Part C — Decisions that belong to the project owner

Nothing here blocks Part B. Each needs a decision, not code — once decided,
record it as an ADR (see `docs/adr/README.md`), then build it.

| ID | Question | Where it came from | Current behaviour |
|---|---|---|---|
| C-1 | Should a **disaster event** be a record of its own? | ADR-0014 gaps | A policy is tied to a region and a period; the event exists only in the policy's name |
| C-2 | Is there a **longest allowed period** for a coordinator's auto-approval? | ADR-0014 gaps | An end time is required, but may be far in the future |
| C-3 | Should a coordinator be limited to **their own region**? | ADR-0014 gaps | Any coordinator can create a policy for any region; there is no coordinator-to-region link |
| C-4 | Should the console have a **form to create a policy**? | ADR-0014 gaps | Created through the API; the console only switches policies on and off |
| C-5 | Coverage floor: **60 or 75**? | Review | 60 in both the Makefile and CI (the Makefile used to say 75) |
| C-6 | What state does a unit / person go to when **released**? | Review | Unit → `in_quarters`, person → `available` |
| C-7 | Should the **demo seed policies** have an end time? | ADR-0014 | The seeded Hyderabad and Vijayawada policies are open-ended, which sits oddly with "off unless switched on" |
| C-8 | Should an **unknown setting name** in `.env` stop start-up? | Review | Silently ignored; making it fail loudly could break an existing `.env` |
| C-9 | Who may **grant a delegation**, and what does it allow? | D-069 | The table exists; nothing reads or writes it |

---

## Part D — Features not built

Their database tables and models exist; nothing uses them. Each needs a
decision or a missing piece before it can be built.

| ID | Feature | What is missing |
|---|---|---|
| F-1 | Password reset | Email delivery — there is none |
| F-2 | Email verification | Email delivery |
| F-3 | Email / SMS notifications | A sender. In-app notifications already work |
| F-4 | Notification preferences | Depends on F-3 |
| F-5 | User delegations | Decision C-9 |
| F-6 | Rate-limit event log | A reason to keep one; the table is never written |

---

## Part E — Installer follow-ups

From section 15 of the master plan. Do these after B-8 has shown the
installer works.

| ID | Item |
|---|---|
| I-1 | After certbot edits the nginx site, the `nginx` step wants to write the HTTP-only version back. Make the step accept a certbot-managed file |
| I-2 | MinIO downloads "latest". Pin a version and its hash in each target file |
| I-3 | No backups. Add a step that installs a nightly `pg_dump` timer |
| I-4 | No automatic security updates. Add an `unattended-upgrades` step |
| I-5 | SSH hardening is left out on purpose (it can lock you out). Possible as an opt-in step |
| I-6 | Worker counts are fixed at two per app |
| I-7 | No uninstall command; the manual steps are in section 13 of the master plan |
| I-8 | The app runs as the database owner. A separate, less-privileged runtime role would make the audit table tamper-resistant (see `docs/08-security.md`) |

---

## Part F — Housekeeping

Small, independent, any order.

| ID | Task | How |
|---|---|---|
| H-1 | Open a pull request for the branch and merge it | After B-1 to B-6 pass |
| H-2 | Add a root `.gitattributes` so shell scripts and the Makefile always use LF line endings | `*.sh text eol=lf`, `Makefile text eol=lf`, `*.py text eol=lf`. On Windows the checkout currently converts them to CRLF, which breaks them if run there |
| H-3 | Generate the real `sql/02_tables.sql` (it is a placeholder) | After B-1: `pg_dump --schema-only --no-owner idrm_db > sql/02_tables.sql` |
| H-4 | Bring `docs/MANIFEST.md` up to date | Its file counts are right, but the per-file tables do not list `infra/`, `shared/lifecycle.py`, `shared/geo.py`, `shared/notifications.py`, `shared/services/dispatch_core.py`, `app/core/authz.py`, `docs/index/`, `docs/infra/`, `docs/review/` |
| H-5 | Check the "four KPI cards" wording in `docs/TUTORIAL.md` against the overview page | `docs/05-dashboard-guide.md` says five |
| H-6 | Extend the boundary lint | `scripts/lint_boundaries.py` checks only `dashboard → app`. Add `app → dashboard` and `shared → app / dashboard / fastapi / flask` |
| H-7 | Finish the instruction tree | `CLAUDE.md` and `docs/index/` exist. Still to do: the three-line `Scope / Owner of / See also` header on each leaf document, and a size check in `make lint` (see [INSTRUCTION-HIERARCHY.md](INSTRUCTION-HIERARCHY.md)) |
| H-8 | Remove the duplicate old scripts outside this repository | `~/Downloads/idrm-artifacts`, `idrm-monorepo`, `idrm-scripts-monorepo`, `idrm-dashboard` on the old laptop hold 113 older shell scripts, including four copies of a setup set with passwords written in it. Keep one copy for reference |
| H-9 | Fix one local, untracked file on the old laptop | `docs/.env.production.example` still uses `SECRET_KEY` and `SESSION_COOKIE_SECURE`; the real names start with `DASHBOARD_` |

---

## Part G — Build the privacy design (ADR-0015)

Decided 2026-11-24 ([ADR-0015](../adr/0015-privacy-first-reveal-ladder.md));
nothing built yet. The design is
[PRIVACY-FIRST-DATA-DESIGN.md](../design/PRIVACY-FIRST-DATA-DESIGN.md); the
gaps it closes (G1–G11) are in [IDRM-WORKSPACE-MAP.md](IDRM-WORKSPACE-MAP.md) §3.1.
Do them in order — G-1 to G-3 need no schema change and fix the worst leaks.
Each needs `pg` tests that read like the design's §7 table; none may accept a 500.

| ID | Task | Closes | Design |
|---|---|---|---|
| G-1 | ✏️ **Code written 2026-11-24, not run.** Return `tracking_token` only in the create response | G2 | §8.7 |
| G-2 | ✏️ **Code written 2026-11-24, not run** (with WF3). Providers see only `approved` requests; unless their org is assigned: snapped location, no `requester_id`, no description. Only members of a **verified** organization see or claim anything (gap WF3). To prove it: run `tests/unit/test_privacy.py` and the `pg` tests in `tests/api/test_incident_privacy.py` after B-3 | G1, G3, G4, WF3 | §7, §8.3 |
| G-3 | Strip EXIF on upload (port `idrm-artifacts/code/app/modules/files/imaging.py`); presigned links 5 min | G6 | §8.8 |
| G-4 | One Alembic revision: `incident_contacts`, `pii_reveals`, `consent_records`, new `incidents` columns, urban/rural marker on `regions`; move `guest_contact`, hash tokens | G5, G10 | §9 |
| G-5 | Extend `shared/privacy.py` (exists since G-2: `incident_view`, `snap`) with `may_reveal`, the scrubber, the 72-h grace window (D7) and the ~5 km rural grid (D3); `POST /incidents/{id}/reveal`; break-glass + review list in the console; admins lose default case access (D5) | G1–G5 | §8.2, §8.5, §8.6 |
| G-6 | Deny-list of personal field names in `shared/audit.py` | G7 | §8.9 |
| G-7 | Daily retention job (30-day contacts, 72-h assignee grace) + `legal_hold` | G8, G11 | §8.11 |
| G-8 | HMAC-hash `entity_lists` values and `login_attempts.email` | G9 | §8.10 |
| G-9 | `public_incident_counts` view (k ≥ 5) and a reporting DB role | — | §8.12 |
| G-10 | **Owner task:** legal counsel confirms DPDP "legitimate use" (D6) before launch | — | §14 |

---

## Where things are

| You want | Read |
|---|---|
| Every problem found and how it was fixed | [DISCREPANCY-REGISTER.md](DISCREPANCY-REGISTER.md) |
| The approval decision and its gaps | [ADR-0014](../adr/0014-approval-first.md) |
| Where accepted ADRs differ from the code | [ERRATA.md](../adr/ERRATA.md) |
| How to build a server | [INFRASTRUCTURE-MASTER-PLAN.md](../infra/INFRASTRUCTURE-MASTER-PLAN.md) |
| How the instructions are organised | [INSTRUCTION-HIERARCHY.md](INSTRUCTION-HIERARCHY.md) |
| What changed, in release-note form | `CHANGELOG.md`, section "Unreleased" |

## Progress log

Add a line here each time a task above is finished or a fault is found.

| Date | Task | What happened |
|---|---|---|
| 2026-11-15 | — | Handover written. Nothing in Part B started. |
| 2026-11-24 | Part G | Privacy design accepted (owner: "Adopt defaults"), ADR-0015 written, Part G added. Nothing built. |
| 2026-11-24 | G-1, G-2, WF3 | Code written: `shared/privacy.py`, `verified_member_org_ids` in `app/core/authz.py`, incident router shaping. 32 rule checks passed in plain Python 3.10 (WSL) and all changed files compile. **Not run:** pytest, ruff, the API, the `pg` tests — no Python 3.11 environment or database on this laptop. Run them in B-3. |
