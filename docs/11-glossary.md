# Glossary

> **Scope:** the words used across IDRM.  
> **Owner of:** term definitions.  
> **See also:** [02-architecture.md](02-architecture.md) · [design/DATA-DESIGN.md](design/DATA-DESIGN.md) (§2, data words)

## Identity & access

**Account** — a concrete login on a specific system. One identity may own
many accounts.

**Identity** — the governed principal: a person, contractor, vendor, or
service account. In IDRM, the closest equivalent is a `user`.

**Least Privilege** — the principle that an identity should hold only the
access needed to do its job.

**RBAC** — Role-Based Access Control. Access is granted via roles rather
than to individuals directly.

**Session** — a server-tracked login. Tracked in `user_sessions`. Can be
revoked without invalidating other sessions of the same user.

**Token version** — an integer on `users`. Bumped on password change,
forced logout, or blacklist. Old tokens are rejected.

## Disaster response

**Incident** — a citizen's help request with a location and a priority.

**Dispatch** — assigning a unit or personnel to an incident.

**Personnel status** — the operational state of a provider or volunteer:
`available`, `responding`, `on_scene`, etc.

**Unit** — a team of personnel, an apparatus, or both.

**ICS** — Incident Command System. The standardised command structure used
in emergency response.

**BigBoard** — a wall-mounted dashboard with independently-configurable
widgets for situational awareness.

**Run log** — a record of actions, hours, and personnel for an incident,
training, or event.

**Mutual aid** — an agreement between two organizations to share resources.

## Governance

**Auto-approval** — the system approves certain low-risk incidents or
providers automatically, subject to policy rules and caps.

**Policy** — a row in `auto_approval_policies`. Defines what gets
auto-approved, where, and under what caps.

**Decision** — a row in `auto_approval_decisions`. Records every evaluation
outcome.

**Entity list** — a blocklist, allowlist, or watchlist entry. Matched
against users, emails, IPs, and other identifiers.

**Cap** — a daily limit. Enforced atomically via Redis counters.

**Kill switch** — `AUTO_APPROVAL_ENABLED`. When off, every decision is
recorded as `skipped`.

## Audit

**Audit event** — one row in `audit_logs`. Who, when, what, before, after.

**Immutability** — enforced at the DB level by a `BEFORE UPDATE OR DELETE`
trigger that raises.

**Non-repudiation** — a party cannot deny having performed an action.
Provided by capturing actor and IP on every write.

## Operations

**PostGIS** — the geographic extension for PostgreSQL. Adds `GEOMETRY`,
`ST_DWithin`, and `ST_Covers`.

**GiST index** — a spatial index on a geometry column.

**GIN index** — a generalised inverted index, used for arrays and JSONB.

**Trigram index** — an index for fuzzy text search (`ILIKE '%term%'`).

**Jitter** — a random offset added to a token's lifetime. Spreads token
refreshes across time to avoid CPU spikes.

**Refresh rotation** — issuing a new refresh token on every refresh and
invalidating the old one.

**Reuse detection** — if a used refresh token is presented again, the whole
family is revoked. A theft indicator.

## Acronyms

| Acronym | Expansion |
|---|---|
| ADR | Architecture Decision Record |
| API | Application Programming Interface |
| CAD | Computer Aided Dispatch |
| CSRF | Cross-Site Request Forgery |
| CSP | Content Security Policy |
| CSV | Comma-Separated Values |
| GIN | Generalized Inverted Index |
| GiST | Generalized Search Tree |
| ICS | Incident Command System |
| IDRM | Integrated Disaster Response Management |
| JWT | JSON Web Token |
| RBAC | Role-Based Access Control |
| RPO | Recovery Point Objective |
| RTO | Recovery Time Objective |
| SLA | Service Level Agreement |
| WAL | Write-Ahead Log |
| XSS | Cross-Site Scripting |
