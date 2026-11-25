# Architecture Decision Records

Every significant architectural choice is recorded here as an ADR. The
format follows [Michael Nygard's original proposal](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

## What an ADR is

A short document capturing **one** decision:

- **Context** — what situation forced a choice
- **Decision** — what we chose
- **Consequences** — what follows, good and bad
- **Alternatives** — what we rejected and why

Once accepted, an ADR is not edited. If the *decision* changes, a new ADR
supersedes it. If the code simply differs from what an ADR states, the
correction is recorded in [ERRATA.md](ERRATA.md) — read it alongside the ADRs.

## The list

| # | Title | Status |
|---|---|---|
| [0001](0001-sql-as-source-of-truth.md) | SQL files are the source of truth for the schema | Accepted |
| [0002](0002-audit-in-database.md) | Audit capture lives in the database | Accepted |
| [0003](0003-immutable-audit.md) | The audit table is immutable | Accepted |
| [0004](0004-redis-optional.md) | Redis is an optional cache | Accepted |
| [0005](0005-two-app-monolith.md) | Two-app monolith | Accepted |
| [0006](0006-dashboard-read-mostly.md) | The dashboard is read-mostly | Accepted |
| [0007](0007-auto-approval.md) | Auto-approval is policy-driven and synchronous | Accepted |
| [0008](0008-pydantic-shape-only.md) | Pydantic validates shape, not business values | Accepted |
| [0009](0009-shared-code.md) | Shared code lives in `shared/` | Accepted |
| [0010](0010-server-tracked-sessions.md) | All sessions are server-tracked | Accepted |
| [0011](0011-unified-entity-lists.md) | Entity lists are one unified table | Accepted |
| [0012](0012-scope-based-volunteers.md) | Volunteer enrollment is scope-based | Accepted |
| [0013](0013-jwt-two-token.md) | Two-token JWT with server-side session verification | Accepted |
| [0014](0014-approval-first.md) | Approval comes first; auto-approval is a coordinator's time-boxed regional switch | Accepted |
| [0015](0015-privacy-first-reveal-ladder.md) | Privacy first: hide personal data by default, reveal it by need | Accepted |
| [0016](0016-overview-card-is-the-triage-queue.md) | The console's first card is the triage queue ("Waiting for Approval") | Accepted |

## Reading order

If you are new to the project, read them in this order:

1. **0005** — the two-app monolith (the most consequential decision)
2. **0009** — the shared-code boundary
3. **0013** — the auth design
4. **0004** — why Redis is optional
5. **0007** — how auto-approval works, then **0014** — who may switch it on, and the default when nobody does
6. **0015** — who may see which personal data, and when
7. **0010**, **0011**, **0012**, **0016** — the remaining subsystems
8. **0001**, **0002**, **0003**, **0006**, **0008** — the foundations

## Adding a new ADR

1. Pick the next number in sequence.
2. Copy the structure of the most recent ADR.
3. Fill in Context, Decision, Consequences, Alternatives considered.
4. Add it to the table above.
5. Reference it in a code comment where the decision manifests.

An ADR is not a design doc — it is the record of **one choice**. If you find
yourself writing more than two pages, you are writing a design doc, not an
ADR.
