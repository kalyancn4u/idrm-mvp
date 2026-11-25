# IDRM — Data and policy configuration: defaults, options, reasons

> **Part of:** [DATA-DESIGN.md](DATA-DESIGN.md) (master). Privacy rules come
> from [ADR-0015](../adr/0015-privacy-first-reveal-ladder.md) and
> [PRIVACY-FIRST-DATA-DESIGN.md](PRIVACY-FIRST-DATA-DESIGN.md); approval rules
> from [ADR-0014](../adr/0014-approval-first.md).
>
> **What this is:** what IDRM does with data **if you configure nothing**, every
> setting that changes it, the safe range of each, and why each default was
> chosen.
>
> **Owner of the facts:** `shared/config.py` is the truth for names, defaults
> and ranges; this document explains them. If they ever disagree, the code
> wins — fix this document.
>
> **Status (2026-11-25):** settings marked **Active** are read by code that is
> written but not yet run against a database (PENDING-TASKS Part V). Settings
> marked **Reserved** are checked and documented now, but no code reads them
> until the named task is built.

---

## Contents

1. [How configuration works](#1-how-configuration-works)
2. [If you change nothing: the default behaviour](#2-if-you-change-nothing-the-default-behaviour)
3. [Settings reference](#3-settings-reference)
4. [Policies kept in the database](#4-policies-kept-in-the-database)
5. [What is deliberately not configurable](#5-what-is-deliberately-not-configurable)
6. [Example profiles](#6-example-profiles)
7. [Changing a setting safely](#7-changing-a-setting-safely)
8. [Honest gaps](#8-honest-gaps)

---

## 1. How configuration works

IDRM has **two kinds of configuration**, for two kinds of decision:

| Kind | Where | Who changes it | When it takes effect | Examples |
|---|---|---|---|---|
| **Settings** — how the platform behaves everywhere | Environment variables, normally written in the `.env` file next to the code | Whoever runs the server | On restart | Grid size, grace window, retention days |
| **Policies** — rules for a place and a time | Rows in the database | Coordinators and admins, through the API or console | Immediately | Auto-approval for a flooded district this week; a blocklist entry |

**The `.env` file is the initial configuration file.** Copy `.env.example` to
`.env` and edit it. Each line is `NAME=value`; names are UPPER_CASE.

Where a value comes from, highest priority first:

1. a real environment variable (e.g. set by systemd or Docker);
2. the line in `.env`;
3. the default written in `shared/config.py`.

So **an empty `.env` still works**: every setting has a safe default.

Three rules protect you from mistakes:

- **Out of range refuses to start.** `PRIVACY_COARSE_GRID_DEGREES=1.0` stops
  the app with a message, rather than being quietly clamped. A privacy setting
  that silently means something else is worse than one that will not load.
- **Contradictions refuse to start.** Two cross-checks (§3.6).
- **Production refuses development secrets.** With `APP_ENV=production` the
  app will not start while known default passwords or keys are in use
  (existing behaviour, `insecure_defaults()`).

Settings are read once per process, so **restart both apps** (API and console)
after a change.

---

## 2. If you change nothing: the default behaviour

The life of one request, with every default in place:

| Moment | What happens to the data | Setting behind it |
|---|---|---|
| A guest submits a request | Stored with its exact point; the guest gets a tracking token **once** | — (ADR-0015, fixed) |
| No auto-approval policy covers the region | Waits in `created`; **no provider sees it** | Policies (§4); ADR-0014 |
| A coordinator approves | Providers in **verified** organizations see type, urgency, a location snapped to **0.01° (~1.1 km)** and a **summary of up to 140 characters with phone numbers, emails and links removed**; not the full description, not the requester | `PRIVACY_COARSE_GRID_DEGREES`, `PRIVACY_SUMMARY_MAX_CHARS` |
| A provider's organization accepts | That organization sees the exact point and description | — (fixed) |
| A photo is uploaded, later opened | Download link works for **5 minutes** | `FILE_LINK_TTL_SECONDS` |
| Something is audited | Personal fields (email, phone, description, …) stored as `"[redacted]"` | `AUDIT_REDACT_EXTRA_KEYS` can add fields |
| The request is completed / verified / cancelled | The assigned organization keeps the full view for **72 hours**, then sees the coarse card | `PRIVACY_ASSIGNEE_GRACE_HOURS` |
| 30 days after closing | *Planned:* contact details deleted, exact point coarsened. **Not yet automatic** — needs G-7 | `RETENTION_*` (Reserved) |
| Public or partner reports | *Planned:* counts only, groups under **5** hidden. Needs G-9 | `PRIVACY_K_ANONYMITY` (Reserved) |

---

## 3. Settings reference

Columns: **Default** · **Allowed** (outside this, start-up fails) ·
**Status** · **What it does** · **Raise / lower it when…**

### 3.1 Privacy — Active

| Setting | Default | Allowed | Status | What it does | Raise / lower it when… |
|---|---|---|---|---|---|
| `PRIVACY_COARSE_GRID_DEGREES` | `0.01` (~1.1 km) | 0.005 – 0.1 | Active | Grid that a provider's coarse location is snapped to; also the grid the nearby search measures from, so the exact point cannot be found by shrinking the radius | **Raise** (0.02–0.05) in sparse areas where one cell holds one house. **Lower** (0.005) only for dense cities where 1 km is too vague to plan — never below, it nears exact |
| `PRIVACY_ASSIGNEE_GRACE_HOURS` | `72` | 0 – 720 | Active | After a request closes, how long the assigned organization keeps the full view for follow-up | **Lower** (24) if follow-up rarely happens. **0** = coarse as soon as it closes. Must not exceed the contact retention (§3.6) |

| `PRIVACY_SUMMARY_MAX_CHARS` | `140` | 40 – 500 | Active | Longest `summary` shown in an incident response: the description with phone numbers (6+ digits, or 5+ number words in English), emails and links replaced by `[number]`, `[email]`, `[link]`, cut at a word | **Raise** (250) if providers cannot judge the need. **Lower** (80) for sensitive populations — the scrubber misses names, addresses and numbers written in Indian-language words, and a shorter summary leaks less of what it misses |

*What the summary hides and misses:* it hides mobile and landline numbers,
Aadhaar-style numbers, emails and links. It deliberately also hides PIN codes
and dates (6+ digits — the safe side) and keeps short numbers ("3 people",
"flat 302", ages). It **misses** names, street addresses and numbers written in
Hindi, Telugu or other words. Only providers in verified organizations see it;
the full text still waits for assignment.

*How the grace window is measured today:* from the request's `updated_at`,
which for a closed request is the closing step. A real `closed_at` column
arrives with G-4.

### 3.2 Files — Active

| Setting | Default | Allowed | Status | What it does | Raise / lower it when… |
|---|---|---|---|---|---|
| `FILE_LINK_TTL_SECONDS` | `300` (5 min) | 60 – 3600 | Active | Lifetime of a download link for an uploaded file. Anyone holding the link can open the file until then | **Raise** (900) only if users on very slow networks cannot finish a download. Was 3600 before ADR-0015 |
| `FILE_MAX_BYTES` | `10485760` (10 MB) | — | Active (existing) | Largest upload accepted; the database also enforces 10 MB | Lower to save storage |
| `IMAGE_MAX_DIMENSION` | `1920` | — | **Declared, unused** | Meant for resizing photos on upload; nothing resizes yet (G-3) | — |

### 3.3 Audit — Active

| Setting | Default | Allowed | Status | What it does | Raise / lower it when… |
|---|---|---|---|---|---|
| `AUDIT_REDACT_EXTRA_KEYS` | empty | comma-separated field names | Active | **Adds** field names whose values are masked in the audit log, on top of the built-in list (`email`, `phone`, `guest_contact`, `description`, `location`, `latitude`, `longitude`, `address`, `review`, `password`, `token`, `tracking_token`, `refresh_token`, `entity_value`, any `contact_…`) | Add a field the moment a new feature might log a personal value, e.g. `aadhaar,vehicle_no`. It **cannot remove** built-in names |

### 3.4 Privacy — Reserved (read when the task is built)

| Setting | Default | Allowed | Used by | What it will do |
|---|---|---|---|---|
| `PRIVACY_RURAL_GRID_DEGREES` | `0.05` (~5.5 km) | 0.005 – 0.5, and ≥ the coarse grid | G-4 / G-5 (ADR-0015 D3) | Coarse grid for regions marked rural |
| `PRIVACY_K_ANONYMITY` | `5` | 2 – 100 | G-9 | Smallest group a public or partner count may show; smaller groups are merged or hidden |
| `PRIVACY_REVEAL_LIMIT_PER_HOUR` | `20` | 1 – 500 | G-5 | Phone reveals one person may make per hour; stops bulk harvesting |
| `PRIVACY_REVEAL_TTL_HOURS` | `24` | 1 – 168 | G-5 | How long one reveal stays valid before tapping again |

### 3.5 Retention, in days — Reserved for G-7

**Nothing is deleted automatically yet.** These are the agreed defaults
(ADR-0015 D4 and privacy design §8.11) that the daily retention job will
read. The audit log is never touched by this job.

| Setting | Default | Allowed | Clock starts | Action |
|---|---|---|---|---|
| `RETENTION_CONTACT_DAYS` | 30 | 1 – 3650 | request closes | delete name, phone, vulnerability flags |
| `RETENTION_EXACT_LOCATION_DAYS` | 30 | 1 – 3650 | request closes | replace the exact point with the coarse one |
| `RETENTION_FREE_TEXT_DAYS` | 90 | 1 – 3650 | request closes | replace description and notes with the summary |
| `RETENTION_PHOTO_DAYS` | 30 | 1 – 3650 | request closes | delete the file and its record |
| `RETENTION_MESSAGE_DAYS` | 90 | 1 – 3650 | sent | delete chat and direct messages |
| `RETENTION_NOTIFICATION_DAYS` | 30 | 1 – 3650 | sent | delete notifications |
| `RETENTION_LIVE_LOCATION_DAYS` | 7 | 1 – 365 | recorded | delete responder location history |
| `RETENTION_SESSION_DAYS` | 90 | 1 – 3650 | session expires | delete |
| `RETENTION_LOGIN_ATTEMPT_DAYS` | 90 | 1 – 3650 | attempt | delete |
| `RETENTION_REVEAL_LOG_DAYS` | 365 | 30 – 3650 | reveal | delete the reveal record |
| `RETENTION_DEACTIVATED_ACCOUNT_DAYS` | 365 | 30 – 3650 | account deactivated | pseudonymise (name → "Former user", email and phone cleared) |

A `legal_hold` flag on a request (G-4) will pause every clock for it.

**Choosing the numbers.** Shorter = less harm if data leaks, less time for
follow-up, complaints and audits. 30 days after closing covers a typical
"did help really arrive?" follow-up. Confirm the final numbers with legal
counsel (G-10).

### 3.6 Cross-checks (start-up fails if broken)

| Rule | Why |
|---|---|
| `PRIVACY_RURAL_GRID_DEGREES` ≥ `PRIVACY_COARSE_GRID_DEGREES` | Rural cells hold fewer homes, so they need the coarser grid, never a finer one |
| `PRIVACY_ASSIGNEE_GRACE_HOURS` ≤ `RETENTION_CONTACT_DAYS` × 24 | Otherwise the contact details would be deleted while the grace window still promises them |

### 3.7 Related settings documented elsewhere

| Settings | Where explained |
|---|---|
| `JWT_*`, `SESSION_*` (token lifetimes, session limits, idle timeouts per role) | [13-auth-and-sessions.md](../13-auth-and-sessions.md) |
| `AUTO_APPROVAL_ENABLED` and the cache TTLs | [12-governance.md](../12-governance.md) and §4 below |
| `DATABASE_URL*`, `REDIS_URL`, `S3_*`, `DASHBOARD_*`, `ADMIN_INITIAL_PASSWORD`, `TRUST_FORWARDED_FOR` | `.env.example` comments; [07-operations.md](../07-operations.md) |

---

## 4. Policies kept in the database

These change during an emergency, so they are data, not settings.

| Policy | Default if nobody acts | How to change it | Reference |
|---|---|---|---|
| **Approval** | Every request waits for a coordinator | A coordinator creates an auto-approval policy for one or more regions **with an end time** (`POST /policies`), then switches it on or off in the console (`/policies`) | ADR-0014 |
| **Auto-approval master switch** | On (`AUTO_APPROVAL_ENABLED=1`) — but with no policy in force it approves nothing, so the effective default is still "wait for a coordinator" | Set `AUTO_APPROVAL_ENABLED=0` to stop all automatic approval at once (decisions are still recorded, as `skipped`) | 12-governance.md |
| **Organization trust** | A new organization is **unverified**; its members see no requests | A coordinator verifies it (console `/organizations`) | ADR-0015, gap WF3 |
| **Blocklists / allowlists** | Empty | Coordinators or admins add entries (console `/policies/entity-lists`). The value is kept in the list, not in the audit log | 12-governance.md |
| **Regions** | Loaded by the seed / regions SQL | Admin task; a request outside every region gets no region and is not auto-approved | 12-governance.md |

**Demo data note:** the seed creates verified organizations and two
open-ended auto-approval policies (Hyderabad, Vijayawada) so the demo works.
A real deployment should not keep open-ended policies (open question C-7).
Seed contents: [SEED_REFERENCE.md](../SEED_REFERENCE.md).

---

## 5. What is deliberately not configurable

Some rules are product decisions recorded in ADRs. Making them a switch would
let one wrong `.env` line undo a decision that protects people, so they are
code, changed only by a new ADR:

| Rule | Decided in |
|---|---|
| Providers never see a request before it is approved | ADR-0014, ADR-0015 |
| A provider must belong to a verified organization to see or claim requests | ADR-0015 (WF3) |
| Providers never see the requester's account id | ADR-0015 |
| The guest tracking token is shown only once | ADR-0015 |
| The audit log is append-only, and the built-in personal fields are always masked | ADR-0003, ADR-0015 |
| The four roles | CLAUDE.md rule 3 |

---

## 6. Example profiles

Starting points, not prescriptions. Each is a few lines in `.env`.

**Default (pilot in one city)** — change nothing.

**Large disaster across rural districts** — coarser cells so a cell is not one
house; a shorter grace window because many organizations rotate through:

```ini
PRIVACY_COARSE_GRID_DEGREES=0.02
PRIVACY_ASSIGNEE_GRACE_HOURS=24
```

**Strict privacy (sensitive population, e.g. a shelter for survivors of violence)**:

```ini
PRIVACY_COARSE_GRID_DEGREES=0.05
PRIVACY_ASSIGNEE_GRACE_HOURS=0
FILE_LINK_TTL_SECONDS=120
AUDIT_REDACT_EXTRA_KEYS=shelter_name,case_ref
RETENTION_CONTACT_DAYS=7
RETENTION_EXACT_LOCATION_DAYS=7
```

**Slow networks (field teams on 2G)** — longer links so downloads finish:

```ini
FILE_LINK_TTL_SECONDS=900
```

---

## 7. Changing a setting safely

1. Edit `.env` (or the service's environment). Keep a note of the old value.
2. Restart the API and the console. If a value is out of range, start-up
   stops and names the setting — fix it and restart.
3. Check the effect: e.g. call `GET /incidents` as a verified provider and
   read `location_grid_km` in the response.
4. Record the change and the reason in your operations log. **Setting
   changes are not written to the audit log** — the application cannot see
   who edited a file on the server.

---

## 8. Honest gaps

- **Not run yet.** The Active settings are read by code that has passed
  hand-checks only; see PENDING-TASKS Part V (V-1, V-5).
- **Reserved settings do nothing yet.** They are validated so the agreed
  numbers live in one place, ready for G-4, G-5, G-7 and G-9.
- **`IMAGE_MAX_DIMENSION` is unused** — no image resizing exists (G-3, X10).
- **Unknown names are ignored.** A misspelt name in `.env`
  (`PRIVACY_GRACE_HOURS=24`) is silently ignored and the default applies
  (open question C-8). Check the spelling against `.env.example`.
- **Grace window uses `updated_at`** until G-4 adds `closed_at`.
