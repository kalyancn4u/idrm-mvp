# instructions.md — pointers and the data-design brief

Start with [CLAUDE.md](CLAUDE.md) (rules + which index to open). This file adds
two things: **pointers** to reference documents that save re-reading the
workspace, and the **brief** that every data-design document must satisfy.

## 1. Pointers

| Need | Open | Why it saves time |
|---|---|---|
| What the other `~/Downloads/idrm-*` folders are, which one is current, where the PRD/FS live, known gaps | [docs/review/IDRM-WORKSPACE-MAP.md](docs/review/IDRM-WORKSPACE-MAP.md) | Replaces scanning six folders (≈2,800 files) |
| **Everything about data**: model, security, privacy, engineering, warehousing, quality, governance, data across the SDLC, MVP → FFP | [docs/design/DATA-DESIGN.md](docs/design/DATA-DESIGN.md) | The master document; the brief in §2 is its contract |
| Privacy in depth: who sees which personal field and when (reveal ladder), retention, DPDP | [docs/design/PRIVACY-FIRST-DATA-DESIGN.md](docs/design/PRIVACY-FIRST-DATA-DESIGN.md) | Detail part of the master; ACCEPTED as [ADR-0015](docs/adr/0015-privacy-first-reveal-ladder.md) |
| What each user does, step by step, and what data each step reads, writes and reveals | [docs/design/DATA-WORKFLOWS.md](docs/design/DATA-WORKFLOWS.md) | Workflow cards W1–W27; gaps WF1–WF3 |
| What is left to build | [docs/review/PENDING-TASKS.md](docs/review/PENDING-TASKS.md) (Part G = privacy) | — |

## 2. The data-design brief

Use this brief when writing or changing any data-design document, so the set
stays complete, consistent and readable.

### 2.1 Objective

Give one place where anyone, starting from zero, can understand **all of
IDRM's data** — what it is, why it is held, how it is protected, how it flows,
how it is analysed, and how it is handled at every stage of building and
running the product — and reach the level where they can make and defend
data decisions themselves. Cover both the **MVP** (one PostgreSQL database)
and the **FFP** (full-fledged product: services, warehouse, national scale).

### 2.2 Audience and voice

- A complete novice must be able to follow it; an expert must find it correct.
- Define each technical term once, in plain words, the first time it appears.
- Explain *why* before *how*. Give a concrete IDRM example for each idea.
- Use a diagram where a picture is clearer than prose (Mermaid or ASCII).
- Be concise: one table beats three paragraphs; no padding, no marketing.
- Be skeptical: say what can go wrong with each choice, and its cost.

### 2.3 Scope — the document must cover

| # | Area | Must answer |
|---|---|---|
| 1 | **Product context (PRD/FS)** | Which product needs create which data; who uses it and for what |
| 2 | **Data inventory and model** | Every entity, its group, its owner, its sensitivity; conceptual → logical → physical |
| 3 | **Privacy-first** | Hide by default, reveal by need; tiers; reveal ladder; consent; retention; rights (summary + link to the privacy part) |
| 4 | **Data security** | Threats; access control (app and database); encryption in transit / at rest / fields; keys and secrets; integrity; audit; backup and recovery; breach response |
| 5 | **Data engineering** | How data moves: ingestion, validation, events/outbox, change data capture, batch vs stream, idempotency, schema evolution, orchestration, observability |
| 6 | **Data warehousing and analytics** | Why OLTP ≠ analytics; dimensional model (facts, dimensions, slowly changing dimensions); metrics; privacy-safe analytics; MVP reporting schema → FFP warehouse/lake |
| 7 | **Data quality and governance** | Quality dimensions and checks; contracts; lineage; catalogue; ownership (RACI); data-protection roles |
| 8 | **Data across the SDLC** | Requirements → design → build → test → release → operate → retire: what data work and which checks happen at each stage |
| 9 | **Operations** | Retention jobs, backups and restore drills, monitoring, capacity, disaster recovery (RPO/RTO) |
| 10 | **MVP → FFP roadmap** | What is built now, what later, and the trigger for each step |
| 11 | **Today vs target** | Honest gap list against the current code, with the fix order |
| 12 | **Decisions** | Open questions with options, a recommended default, and the reason |
| 13 | **End-user workflows** | For each person (guest, citizen, provider, coordinator, admin, public/analyst): each task step by step — what they do, which screen or endpoint, what data is read and written (with tier), who can then see it, what is audited, what can go wrong — Today and target |

Out of scope: UI design, non-data infrastructure detail (see
`docs/infra/INFRASTRUCTURE-MASTER-PLAN.md`), legal advice.

### 2.4 Rules for the content

1. **Label every claim's status:** *Today* (read in the code), *Accepted*
   (decided in an ADR, not necessarily built), *Proposed* (needs an owner
   decision), *FFP* (later). Never present a proposal as built.
2. **Say what was verified and how.** "Read in the code" is not "ran it".
3. **The code is the truth for today; the specs** (`~/Downloads/idrm-artifacts/docs/mvp`,
   `docs/ffp`) **are the truth for intent.** Where they disagree, list it as a gap.
4. **One owner per fact.** The privacy detail lives in the privacy part; the
   master summarises and links. Table counts live in `docs/03-data-model.md`.
5. **Respect the project rules** in CLAUDE.md: schema change = new Alembic
   revision; four roles only; state changes via `shared/lifecycle.py`;
   audit every state change; no secret in the repo.
6. **Decisions become ADRs** only after the owner answers, quoting the owner.
   Accepted ADRs are not edited; corrections go to `docs/adr/ERRATA.md`.
7. **Open questions go to the owner with options**, each explained for a
   beginner, the recommended default first.

### 2.5 Shape of the document set

```
docs/design/
├── DATA-DESIGN.md ................ master: all thirteen areas, MVP and FFP
├── PRIVACY-FIRST-DATA-DESIGN.md .. part: privacy in depth (ADR-0015)
└── DATA-WORKFLOWS.md ............. part: end-user workflows, data step by step (area 13)
```

Add a new part only when a section of the master grows beyond about two
screens and has its own audience; link it from the master's contents.

## 3. Status (2026-11-24)

- Privacy design: **ACCEPTED** (owner adopted defaults D1–D7, ADR-0015),
  **not built** — build steps are PENDING-TASKS Part G.
- Master data design: written 2026-11-24 to the brief above; its own open
  decisions are in its last section and are **Proposed** until the owner answers.
- Nothing in either document has been run against a database.
