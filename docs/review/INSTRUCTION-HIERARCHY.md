# Instruction Hierarchy — a B+ tree for the docs

> **Scope:** how the instruction files are organised: CLAUDE.md → index file → leaf.  
> **Owner of:** the rules for root, index and leaf files (checked by `scripts/lint_docs.py`).  
> **See also:** [../../CLAUDE.md](../../CLAUDE.md) · [../index/QUALITY.md](../index/QUALITY.md)

## Status (updated 2026-11-25) — implemented except step 5

| Part of the proposal | State |
|---|---|
| Root file `CLAUDE.md` | **Exists.** About 840 tokens, not the 400 proposed below: it also carries ten standing rules and five working habits, because a new machine has no other memory of them |
| Seven branch files in `docs/index/` | **Exist.** 170 to 350 tokens each, pointers only, each with a "one place each fact is written" table |
| Pending work routed from the root | **Done** — `CLAUDE.md` points at `PENDING-TASKS.md` |
| Three-line `Scope / Owner of / See also` header on each leaf | **Done 2026-11-25** — on all 30 leaves (accepted ADRs excepted, see below) |
| Size, reachability and link check in `make lint` | **Done 2026-11-25** — `scripts/lint_docs.py`, also run by CI |
| Repeated facts replaced by links | Partly — the facts were corrected in every copy during the review, but the copies still exist |

**How the check differs from the proposal below, and why:**

| Proposal | As built | Reason |
|---|---|---|
| Root ≤ 400 tokens | Root ≤ 900 | The decision above: the root also holds the standing rules |
| Each branch ≤ 250 | Each branch ≤ 350 | Room for one line per document as the data-design documents were added; `DATA.md` was trimmed to fit rather than given an exception |
| Every leaf reachable from **exactly** one branch | From **at least** one; two parents are printed as a note | The data and privacy designs genuinely belong to both the data and the security topic. Forcing one parent would hide them from half their readers |
| Header on every leaf | Every leaf except accepted ADRs (`docs/adr/0*.md`) and the documents for people (README, TUTORIAL, DEMO_SCRIPT, DIAGRAMS, MANIFEST) | Accepted ADRs are never edited (CLAUDE.md); documents for people are read only on request |
| No broken links | Every relative link must point at an existing file; links inside code blocks and inline code are ignored; `#anchors` are not checked | Anchors depend on how each viewer turns headings into ids; checking them would give false alarms |

The rest of this document is the original proposal, kept as the reasoning.

## What was found

This repository has **no `instructions*.md` and no `CLAUDE.md`**. The
instructions an assistant (or a new developer) would follow are spread over 40
markdown files, about **43 700 tokens** in total (estimated at 4 characters per
token). There is no single entry point that says "for task X read only file Y",
so the safe choice today is to read a lot, and the same fact is repeated in
several files — which is how the documents drifted apart (see D-051 to D-067 in
`DISCREPANCY-REGISTER.md`).

| Group | Files | Approx. tokens |
|---|---|---|
| Root (`README`, `CONTRIBUTING`, `CHANGELOG`) | 3 | 4 500 |
| Numbered guides `docs/01`–`13` | 13 | 12 200 |
| Long references (`CLIENT_EXAMPLES`, `DIAGRAMS`, `MANIFEST`, `DEPLOYMENT_CHECKLIST`, `SECURITY_VERIFICATION`, `TUTORIAL`, `QUICK_REFERENCE`, `DEMO_SCRIPT`, `SEED_REFERENCE`) | 9 | 22 200 |
| ADRs + ADR index | 14 | 4 200 |
| `docs/README.md` | 1 | 500 |

## The idea in plain words

A **B+ tree** is the structure databases use to find one row without scanning
the table. It has three properties worth copying:

1. **Upper nodes hold only keys and pointers, never data.** They are small, so
   reading them is cheap.
2. **All data lives in the leaves.** Each fact is stored once.
3. **Leaves are linked to their neighbours**, so a reader who lands on one leaf
   can step sideways without going back to the top.

Applied to instructions: the root and the branch files only say *where to go*;
the leaf files hold the rules; each leaf ends with a "see also" line.

## Proposed tree

```
CLAUDE.md                          ROOT    ≤ 400 tokens, always loaded
│   stack, 5 hard rules, routing table (task → one branch file)
│
├── docs/index/BUILD.md            BRANCH  ≤ 250 tokens each, pointers only
│   ├── leaf: docs/01-getting-started.md
│   ├── leaf: docs/07-operations.md
│   ├── leaf: docs/10-troubleshooting.md
│   └── leaf: docs/DEPLOYMENT_CHECKLIST.md
│
├── docs/index/API.md
│   ├── leaf: docs/04-api-reference.md
│   ├── leaf: docs/13-auth-and-sessions.md
│   └── leaf: docs/CLIENT_EXAMPLES.md
│
├── docs/index/DASHBOARD.md
│   ├── leaf: docs/05-dashboard-guide.md
│   └── leaf: docs/06-design-system.md
│
├── docs/index/DATA.md
│   ├── leaf: docs/03-data-model.md
│   ├── leaf: docs/SEED_REFERENCE.md
│   └── leaf: docs/12-governance.md
│
├── docs/index/SECURITY.md
│   ├── leaf: docs/08-security.md
│   └── leaf: docs/SECURITY_VERIFICATION.md
│
├── docs/index/QUALITY.md
│   ├── leaf: docs/09-testing.md
│   ├── leaf: CONTRIBUTING.md
│   └── leaf: docs/review/DISCREPANCY-REGISTER.md
│
└── docs/index/WHY.md              (decisions; read only when asked "why")
    ├── leaf: docs/02-architecture.md
    ├── leaf: docs/adr/0001 … 0013
    └── leaf: docs/11-glossary.md
```

Human-only material (`README.md`, `TUTORIAL.md`, `DEMO_SCRIPT.md`,
`DIAGRAMS.md`, `MANIFEST.md`, `QUICK_REFERENCE.md`, `CHANGELOG.md`) stays where
it is but is **not routed to** from the root, so an assistant never loads it
unless a person asks for it by name.

## Rules for each level

**Root (`CLAUDE.md`)** — loaded on every session, so every line costs tokens
every time.
- Stack in one line each; the few rules that apply to every task (for example
  "dashboard must not import app", "schema changes go through Alembic").
- A routing table: *task keyword → branch file*. Nothing else.
- No examples, no rationale, no copies of leaf content.

**Branch (`docs/index/*.md`)** — one per topic.
- One line per leaf: `file — what question it answers — rough size`.
- For large leaves, list section anchors so a reader can open one section
  instead of the whole file (`CLIENT_EXAMPLES.md#refresh` rather than all
  4 000 tokens).
- No rules of its own. If a branch file starts explaining, move that text to a
  leaf.

**Leaf** — the only place a fact may be written.
- Starts with a three-line header: `Scope:` (what it covers), `Owner of:`
  (facts this file is the single source for), `See also:` (sibling leaves —
  the B+ tree's sideways links).
- Any other file that needs the fact links to it instead of repeating it.

## Example root file

```markdown
# IDRM MVP
FastAPI API (app/, :8000) + Flask console (dashboard/, :5000) + shared/ ; Postgres 16 + PostGIS ; Redis optional.

## Always
- dashboard/ and app/ never import each other; common code goes in shared/.
- Schema changes: new Alembic revision only. sql/ is a read-only mirror.
- Every state change writes an audit row.
- Roles: citizen, provider, coordinator, admin. Nothing else.

## Where to read (open ONE, then only the leaf it names)
| Task | Read |
|---|---|
| install, run, deploy, fix a broken setup | docs/index/BUILD.md |
| add or change an API endpoint, tokens | docs/index/API.md |
| console pages, styling | docs/index/DASHBOARD.md |
| tables, seed data, auto-approval | docs/index/DATA.md |
| permissions, threat model | docs/index/SECURITY.md |
| tests, lint, known defects | docs/index/QUALITY.md |
| "why is it built this way" | docs/index/WHY.md |
```

## What it saves

Estimates from the measured file sizes; not measured in a live session.

| Task | Today (no router) | With the tree |
|---|---|---|
| Add an API endpoint | `README` + `02` + `04` + `13` + `08` ≈ 6 200 | root 400 + `API.md` 250 + `04` 1 350 ≈ **2 000** |
| Fix a failing setup | `README` + `01` + `07` + `10` ≈ 5 000 | 400 + 250 + `10` 1 300 ≈ **1 950** |
| Change a policy rule | `README` + `12` + `08` + ADR-0007/0008 ≈ 4 700 | 400 + 250 + `12` 600 ≈ **1 250** |
| Worst case, read everything | ≈ 43 700 | unchanged, but no task should need it |

The larger gain is correctness: with one owner per fact, items like the login
URL (written in five places, wrong in four) can only be wrong in one.

## Single-owner table to apply first

These facts are currently repeated and disagree. Pick the owner, delete or
link the copies.

| Fact | Owner leaf | Copies to turn into links |
|---|---|---|
| Console login URL | `docs/05-dashboard-guide.md` | `README`, `bootstrap.sh`, `run_all.sh`, `smoke.sh` |
| Role list and TTL table | `docs/13-auth-and-sessions.md` | `README`, `.env.example` comments, `docs/08` |
| Endpoint list | `docs/04-api-reference.md` (better: generate from `/openapi.json`) | `QUICK_REFERENCE`, `CLIENT_EXAMPLES` |
| Table and migration counts | `docs/03-data-model.md` | `README`, `sql/02_tables.sql`, `MANIFEST` |
| Password hashing | `docs/08-security.md` | `docs/13`, `SECURITY_VERIFICATION` |
| Lifecycle diagram | `docs/04-api-reference.md` | `README`, `DIAGRAMS`, `QUICK_REFERENCE` |
| Setting names (`DASHBOARD_SECRET_KEY`, …) | `.env.example` | `docs/07`, `docs/08`, `docs/10`, `QUICK_REFERENCE`, `DEPLOYMENT_CHECKLIST` |
| Seed contents | `docs/SEED_REFERENCE.md` | `README`, `docs/01`, `sql/06` header |
| Revocation timing (immediate vs 60 s) | `docs/13-auth-and-sessions.md` | `README`, ADR-0010, ADR-0013 |

## Steps to adopt

1. Fix the facts first (D-051 to D-067), otherwise the tree just routes to
   wrong text faster.
2. Create `CLAUDE.md` from the example above.
3. Create the seven `docs/index/*.md` branch files, pointers only.
4. Add the three-line header to each leaf.
5. Replace repeated facts with links, using the single-owner table.
6. Add a check to `make lint`: root ≤ 400 tokens, each branch ≤ 250, every
   leaf reachable from exactly one branch, no broken links.
