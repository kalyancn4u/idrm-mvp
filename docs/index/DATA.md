# Data, seed, governance — index

Index only: it tells you which document answers a question. It contains no
rules of its own. Open the ONE document you need; for a long one, go to the
section named. Back to [CLAUDE.md](../../CLAUDE.md).

| Document | Answers | ~tokens |
|---|---|---:|
| [03-data-model.md](../03-data-model.md) | The 60 tables by group; enums | 800 |
| [SEED_REFERENCE.md](../SEED_REFERENCE.md) | What `make seed` creates | 1,200 |
| [12-governance.md](../12-governance.md) | Auto-approval, policies, entity lists | 1,300 |
| [DATA-DESIGN.md](../design/DATA-DESIGN.md) | Master data design; gaps X1–X11 | 11,000 |
| [PRIVACY-FIRST-DATA-DESIGN.md](../design/PRIVACY-FIRST-DATA-DESIGN.md) | Who sees which personal field, when (ADR-0015) | 9,000 |
| [DATA-WORKFLOWS.md](../design/DATA-WORKFLOWS.md) | Each user's tasks, step by step | 9,000 |
| [DATA-CONFIGURATION.md](../design/DATA-CONFIGURATION.md) | Privacy and retention settings | 4,500 |
| [IDRM-WORKSPACE-MAP.md](../review/IDRM-WORKSPACE-MAP.md) | The other `idrm-*` folders; gaps G1–G12 | 2,000 |

## The one place each fact is written

| Fact | Owner |
|---|---|
| Table and migration counts | 03-data-model.md |
| Seed contents | SEED_REFERENCE.md |
| Policy rules and approval-first | 12-governance.md + ADR-0014 |
| Privacy and retention settings | `shared/config.py`; explained in DATA-CONFIGURATION.md |
