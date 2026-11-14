# ADR Errata — where an accepted ADR and the code differ

An accepted ADR is not edited (see [README](README.md)). When the code turns
out to differ from what an ADR says, the difference is recorded here instead,
so a reader of the ADR is not misled. A change of *decision* still needs a new
ADR; this page is only for corrections of fact.

Checked against the code on 2026-11-14.

| ADR | What it says | What is true |
|---|---|---|
| [0001](0001-sql-as-source-of-truth.md) | Title: "SQL files are the source of truth for the schema" | Its own decision text says the schema lives in the **Alembic migrations**; `sql/` is a readable mirror, and `sql/02_tables.sql` is still an empty placeholder |
| 0001 | "Autogenerate is safe" | Safe only since `alembic/env.py` gained an `include_object` filter. Four tables (`api_keys`, `geocode_cache`, `webhook_subscriptions`, `webhook_deliveries`) have no ORM model; without the filter autogenerate would have proposed dropping them |
| [0002](0002-audit-in-database.md) | Title: "Audit capture lives in the database" | The **application** writes audit rows (`shared/audit.py`). Only *immutability* is enforced in the database, by a trigger |
| [0003](0003-immutable-audit.md) | "Anyone — app, DBA, rogue script — cannot tamper" | `UPDATE` and `DELETE` are blocked. `TRUNCATE` still works (ADR-0002 says so deliberately), and a role that owns the table can drop the trigger. See "What the trigger does not stop" in [08-security.md](../08-security.md) |
| [0004](0004-redis-optional.md) | Without Redis, rate limits "count from `rate_limit_events`" | Without Redis the limiter uses an in-process counter, one per worker. Nothing writes `rate_limit_events` |
| [0006](0006-dashboard-read-mostly.md) | Lists 12 write routes | There are 15: dispatch **assign**, **offer** and **release** are also console writes |
| 0006 | "Add entity list entry — coordinator" | Correct since coordinators were given the `act.policies` permission (2026-11-14); before that the console allowed admin only |
| [0007](0007-auto-approval.md) | Policies are "validated by Pydantic on load and write" | On write since 2026-11-14 (`POST /policies` returns 422 for a malformed policy). The console has no create form |
| 0007 | "One engine serves both incident approval and provider verification" | The engine is called only when an **incident** is created. Provider policies can be stored but are never evaluated |
| 0007 | "Never fail-open. Any evaluation error results in `deferred`" | A full cap, an unknown region and an un-evaluable condition all leave the request for a human. An unexpected exception inside the engine fails the whole create request with 500 rather than deferring |
| 0007 | "`POST /incidents` response gains an `auto_approval` object" | The response has a single boolean field, `auto_approved` |
| [0009](0009-shared-code.md) | "`make lint` is the enforcement mechanism" for the shared boundary | `make lint` checks only `dashboard → app`. That `shared/` must not import `app/`, FastAPI or Flask is a convention; it holds today but nothing checks it |
| [0010](0010-server-tracked-sessions.md), [0013](0013-jwt-two-token.md) | "60-second revocation window (worst case) when Redis caching is active" | Every revocation path now deletes the cached session, and the token version is always read from the database, so revocation takes effect on the next request |
| 0010, 0013 | "Blacklist — same, plus an entity-list entry" | No blacklist flow exists. Force sign-out exists; adding a list entry is a separate manual step |
| 0013 | "If a used refresh token appears again, the whole family is revoked" | True since 2026-11-14, when the presented token does not match a *live* session. A refresh on an already-revoked session is simply refused |
| [0012](0012-scope-based-volunteers.md) | "Approval is by a coordinator of the same scope… `user_delegations` extends it" | Any coordinator can approve any enrollment. `user_delegations` is never read |

Refined by a later ADR rather than corrected here: who may switch
auto-approval on, and the default when nobody does — see
[ADR-0014](0014-approval-first.md).
