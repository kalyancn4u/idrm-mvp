# IDRM workspace map, gaps and references

> **Scope:** the other `~/Downloads/idrm-*` folders, which one is current, and known gaps.  
> **Owner of:** the folder map and privacy gaps G1–G12.  
> **See also:** [../design/DATA-DESIGN.md](../design/DATA-DESIGN.md) · [PENDING-TASKS.md](PENDING-TASKS.md)

> **What this is:** a one-page map of every `~/Downloads/idrm-*` folder on this
> machine, what each one is for, where the important documents live, and what is
> missing or contradictory between them. Read this instead of re-scanning the
> folders: it saves time and tokens in a new conversation.
>
> **Surveyed:** 2026-11-24, by reading folder trees, READMEs, git heads, the
> `idrm-mvp` models and routers, and the privacy sections of the MVP/FFP specs.
> Nothing was run. If a folder has changed since, trust the folder.

---

## 1. The folders at a glance

| Folder | What it is | Git head (2026-11-24) | Status | Use it for |
|---|---|---|---|---|
| **`idrm-mvp`** | **The living MVP code.** FastAPI API + Flask staff console + `shared/`, one PostgreSQL/PostGIS DB, ~60 tables, 4 Alembic revisions | `6ad05f1` 2026-11-15, branch `fix/review-findings-and-approval-first` | Active. Code written, **never run against a database** (see `docs/review/PENDING-TASKS.md`) | Anything about the code that will ship |
| **`idrm-artifacts`** | **The documentation library.** MVP + FFP specs (PRD, scope, architecture, security, data model, API), user guides, code walk-through, an *earlier* 10-module code set in `code/` | `9c08f95` 2026-08-23, `main` | Docs complete; its `code/` is an older, different codebase | Requirements (PRD/FS), the "why", the FFP vision |
| **`idrm-monorepo`** | A Turborepo-style **microservices scaffold** for the FFP: `services/*-service`, `bff-web`, `bff-mobile`, `apps/web-react`, `apps/mobile`, `packages/*` | `2836929` 2026-10-05, `main` | Scaffold + copied docs; mostly stubs | Picture of the FFP split into services |
| **`idrm-dashboard`** | ⚠️ **A different product with the same initials:** "Identity Data & **Risk** Management" — an identity-governance console with Admin and **Auditor** modes | `2306ac9` 2026-10-12, `main` | Separate, self-contained | Ideas for an auditor console; **not** part of disaster response |
| **`idrm-posters`** | 44 vision posters (phases 00–08) + 14 MVP/FFP architecture posters (PNG) | not a git repo | Static | Talks and orientation |
| **`idrm-scripts-monorepo`** | 35 one-off shell scripts that built/migrated the monorepo and fixed its doc links, plus two logs | not a git repo | Finished, historical | Only if re-running that migration |

```
~/Downloads
├── idrm-mvp/ ............ CODE THAT SHIPS (source of truth for behaviour)
├── idrm-artifacts/ ...... SPECS (source of truth for requirements & rationale)
│   ├── docs/mvp/ ........ PRD 10 · scope 11 · security 22 · data 50 · API 40
│   ├── docs/ffp/ ........ the same numbers, for the full-fledged product
│   ├── code/ ............ an EARLIER MVP codebase (10 modules, 6 migrations)
│   └── archive/ ......... retired generations v0–v3, templates, old prompts
├── idrm-monorepo/ ....... FFP microservice scaffold (+ a copy of archive/)
├── idrm-dashboard/ ...... DIFFERENT PRODUCT (identity risk), same acronym
├── idrm-posters/ ........ PNG posters
└── idrm-scripts-monorepo/ scripts that built idrm-monorepo
```

**Rule of thumb:** *what it must do* → `idrm-artifacts/docs/mvp/`;
*what it actually does* → `idrm-mvp/`; *where it is going* → `idrm-artifacts/docs/ffp/`.

---

## 2. Where to find things (reference)

| Question | Open |
|---|---|
| What must the MVP do, for whom? | `idrm-artifacts/docs/mvp/10-requirements-prd.md` |
| What is in / out of MVP scope? (privacy levels are FFP) | `idrm-artifacts/docs/mvp/11-requirements-scope-and-acceptance.md` §3 |
| Security & privacy promises (PII minimisation, DPDP, audit retention) | `idrm-artifacts/docs/mvp/22-architecture-security-and-iam.md` §4–§5, §8 |
| FFP privacy (field encryption, biometrics with consent, privacy levels) | `idrm-artifacts/docs/ffp/22-…` §3, §6 and `ffp/50-data-model.md` |
| Spec'd data model | `idrm-artifacts/docs/mvp/50-data-model.md` |
| Real tables and columns | `idrm-mvp/shared/models/*.py`, `idrm-mvp/alembic/versions/` |
| Who may see which incident (real rule) | `idrm-mvp/app/modules/incidents/router.py` (`_may_view`, `_to_response`) |
| Incident states | `idrm-mvp/shared/lifecycle.py`, ADR-0014 |
| **Master data design** (security, engineering, warehousing, SDLC) | [`idrm-mvp/docs/design/DATA-DESIGN.md`](../design/DATA-DESIGN.md) |
| **Privacy-first data design (target)** | [`idrm-mvp/docs/design/PRIVACY-FIRST-DATA-DESIGN.md`](../design/PRIVACY-FIRST-DATA-DESIGN.md) |
| Unfinished MVP work | `idrm-mvp/docs/review/PENDING-TASKS.md` |

---

## 3. Gap analysis

Severity: 🔴 a person could be harmed or the law broken · 🟠 a promise in the
spec is not kept · 🟡 tidiness, confusion, wasted effort.

### 3.1 Privacy gaps — spec says one thing, `idrm-mvp` code does another

| # | Gap | Evidence | Sev |
|---|---|---|---|
| G1 | **Every provider can see every request**, including ones still waiting for approval (`created`). The spec says contact is shared "with an assigned provider only as needed". | `incidents/router.py` `_may_view` returns True for any provider; `list_incidents` filters only citizens | 🔴 |
| G2 | **`tracking_token` is returned in every incident response**, to providers and staff too. It is a bearer secret: whoever holds it can follow a guest's request. | `_to_response` includes `tracking_token` | 🔴 |
| G3 | **Exact coordinates go to every provider** via `/incidents` and `/incidents/nearby`, before anyone is assigned. | `_to_response` returns `latitude`/`longitude` | 🔴 |
| G4 | **`requester_id` is shown to providers**, so one person's requests can be linked together. | `_to_response` | 🟠 |
| G5 | **The opposite gap: the assigned provider has no way to reach the citizen.** No contact field is ever revealed, even after assignment. Too little sharing can cost a life too. | no reveal path in the router | 🟠 |
| G6 | **Photos keep their EXIF/GPS data.** The spec promises stripping; the older `idrm-artifacts/code` did it (`files/imaging.py`); `idrm-mvp` does not. Presigned links last 1 hour. *Update 2026-11-25:* metadata is now stripped on upload and links last 5 minutes — written and hand-checked, not run in the app (PENDING-TASKS G-3, V-8) | `idrm-mvp/app/modules/files/router.py`, `shared/storage.py` | 🟠 |
| G7 | **The immutable audit log can hold personal data** in `old_values`/`new_values`, and immutable means it can never be erased. | `shared/models/audit.py`, ADR-0003 | 🟠 |
| G8 | **No retention schedule in code.** Only two purge queries, as manual SQL in `docs/07-operations.md`; nothing for incidents, guest phone numbers, chats, notifications, files, live locations. | `docs/07-operations.md` §76–77, `DEPLOYMENT_CHECKLIST.md` "Retention policy is defined" unticked | 🟠 |
| G9 | **Raw emails, phones and IPs stored for matching**: `entity_lists`, `entity_list_matches`, `login_attempts` (even for people who are not users). | `shared/models/governance.py`, `identity.py` | 🟡 |
| G10 | **No record of notice or consent** (what the person was told, when, what they agreed to). DPDP needs this. | no table | 🟠 |
| G11 | **Responder live location has no time limit** (`personnel_statuses.location`). | `shared/models/personnel.py` | 🟡 |
| G12 | Per-request **privacy levels** (Public/Protected/Private) — deferred to FFP by decision 2026-08-12. Not a defect; listed so it is not forgotten. | scope doc §3 | — |

**Update 2026-11-24:** G1–G4 (and workflow gap WF3) have code written under
PENDING-TASKS G-1/G-2 — not yet run against a database. The Evidence column
above describes the code before that change.

All twelve have a proposed fix in
[PRIVACY-FIRST-DATA-DESIGN.md §12](../design/PRIVACY-FIRST-DATA-DESIGN.md#12-from-today-to-target-the-migration-plan).

### 3.2 Workspace gaps

| # | Gap | Sev |
|---|---|---|
| W1 | **Name clash:** `idrm-dashboard` is an identity-risk product, not the IDRM staff console (that is `idrm-mvp/dashboard/`). Easy to mix up. Consider renaming the folder. | 🟡 |
| W2 | **Two different MVP codebases:** `idrm-artifacts/code` (10 modules, 6 migrations, Aug 2026) and `idrm-mvp` (13 modules, ~60 tables, Nov 2026). Only `idrm-mvp` is current. Features that exist only in the old one (EXIF stripping, face-detection gate) should be ported, not lost. | 🟠 |
| W3 | `archive/` is duplicated in full in `idrm-artifacts` and `idrm-monorepo`. | 🟡 |
| W4 | `idrm-mvp/sql/02_tables.sql` is a placeholder; there is no readable schema dump until the code is run once. | 🟡 |
| W5 | `idrm-mvp` docs (`docs/03-data-model.md`) and spec docs (`idrm-artifacts/docs/mvp/50-data-model.md`) describe different table sets; the code is the truth for `idrm-mvp`. | 🟡 |
