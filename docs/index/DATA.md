# Data, seed, governance — index

Index only: it tells you which document answers a question. It contains no
rules of its own. Open the ONE document you need; for a long one, go to the
section named. Back to [CLAUDE.md](../../CLAUDE.md).

| Document | Answers | ~tokens |
|---|---|---:|
| [03-data-model.md](../03-data-model.md) | The 60 tables by group; enums | 800 |
| [SEED_REFERENCE.md](../SEED_REFERENCE.md) | What `make seed` creates | 1,200 |
| [12-governance.md](../12-governance.md) | Auto-approval, policies, caps, entity lists; which conditions are enforced | 1,300 |
| [design/DATA-DESIGN.md](../design/DATA-DESIGN.md) | Master data design: domains, security, data engineering, warehousing/analytics, quality, data across the SDLC, backups, MVP→FFP, gaps X1–X11, decisions E1–E7 (Proposed) | 11,000 |
| [design/DATA-CONFIGURATION.md](../design/DATA-CONFIGURATION.md) | Default data behaviour if nothing is configured; every privacy, file, audit and retention setting with default, range, status and reason; policies kept in the database; what is deliberately not configurable | 4,500 |
| [design/DATA-WORKFLOWS.md](../design/DATA-WORKFLOWS.md) | Every user's tasks step by step: endpoint/page, data read and written, tier, who sees it, audit action; gaps WF1–WF3 | 9,000 |
| [design/PRIVACY-FIRST-DATA-DESIGN.md](../design/PRIVACY-FIRST-DATA-DESIGN.md) | ACCEPTED (ADR-0015), not built: who sees which personal field and when (reveal ladder §7), sensitivity tiers, retention, schema changes, FFP | 9,000 |
| [review/IDRM-WORKSPACE-MAP.md](../review/IDRM-WORKSPACE-MAP.md) | What each `~/Downloads/idrm-*` folder is; privacy gaps G1–G12 in today's code | 2,000 |

## The one place each fact is written

| Fact | Owner |
|---|---|
| Table and migration counts | 03-data-model.md |
| Seed contents | SEED_REFERENCE.md (and `scripts/seed.py`) |
| Policy rules and approval-first | 12-governance.md + ADR-0014 |
| Privacy, file-link, audit and retention settings (names, defaults, ranges) | `shared/config.py`, explained in design/DATA-CONFIGURATION.md |
