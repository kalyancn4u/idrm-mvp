# API Reference

> **Scope:** every API endpoint, who may call it, and who sees which fields.  
> **Owner of:** the endpoint list (the live list is `/docs` on a running API).  
> **See also:** [13-auth-and-sessions.md](13-auth-and-sessions.md) · [CLIENT_EXAMPLES.md](CLIENT_EXAMPLES.md) · [design/DATA-CONFIGURATION.md](design/DATA-CONFIGURATION.md)

Base path: `/api/v1`. Every endpoint needs a bearer token unless its **Auth**
column says `none` or `anon`. The open ones are: `/health`, `/info`,
`POST /incidents` (guest requests), `/incidents/track/{token}`,
`GET /organizations`, and the four `/auth/*` calls.

A filter with an unknown value (for example `?status=opne`) is rejected with
`422 validation_error`. Every response carries an `X-Request-ID` header.

## Authentication

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"secret123","name":"Test User"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"secret123"}'
# → { "user": {...}, "tokens": { "access_token": "...", "refresh_token": "..." } }

# Authenticated request
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8000/api/v1/users/me

# Refresh
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H 'Content-Type: application/json' \
  -d '{"refresh_token":"..."}'
```

## Error envelope

Every error:

```json
{
  "error": {
    "code": "not_found",
    "message": "Incident not found.",
    "details": {}
  }
}
```

Common codes: `validation_error` (422), `unauthorized` (401),
`token_expired` (401), `token_version_mismatch` (401), `forbidden` (403),
`not_found` (404), `invalid_transition` (409), `rate_limited` (429).

---

## Health + info

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/health` | none | Liveness + DB connectivity |
| GET | `/api/v1/info` | none | App name + supported languages |

## Auth

| Method | Path | Body | Purpose |
|---|---|---|---|
| POST | `/auth/register` | `{email, password, name, phone?, role?, language?}` | Create account. `role` may be `citizen` (default) or `provider`; anything else is `403` |
| POST | `/auth/login` | `{email, password}` | Issue tokens |
| POST | `/auth/refresh` | `{refresh_token}` | Rotate tokens |
| POST | `/auth/logout` | `{refresh_token}` | Revoke session |

## Users

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/users/me` | user | Current profile |
| PATCH | `/users/me` | user | Update name/phone/language |
| POST | `/users/me/change-password` | user | Change password |
| GET | `/users/me/sessions` | user | List active sessions |
| DELETE | `/users/me/sessions/{id}` | user | Revoke one session |
| GET | `/users` | admin | List all users |

User detail and role/status changes are done in the staff console, not the API.

## Incidents

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/incidents` | anon or user | Create request. A guest gets `tracking_token` **in this response only** |
| GET | `/incidents` | user | List, scoped by role (see "Who sees what" below) |
| GET | `/incidents/mine` | citizen | My requests |
| GET | `/incidents/track/{token}` | anon | Guest tracking (the token is not echoed back) |
| GET | `/incidents/nearby?latitude=&longitude=&radius_km=` | provider+ | Proximity search; for providers, distance is measured from the ~1 km snapped point |
| GET | `/incidents/{id}` | user | Detail, shaped for the caller |
| GET | `/incidents/{id}/updates` | user | Timeline — full view only; `actor_id` shown to staff only |
| POST | `/incidents/{id}/approve` | coordinator | Approve |
| POST | `/incidents/{id}/reject` | coordinator | Reject |
| POST | `/incidents/{id}/accept` | provider | Claim — only when `approved` ([ADR-0014](adr/0014-approval-first.md)) |
| POST | `/incidents/{id}/start` | provider | Start work |
| POST | `/incidents/{id}/complete` | provider | Mark done |
| POST | `/incidents/{id}/verify` | citizen | Confirm + rate |
| POST | `/incidents/{id}/cancel` | citizen/coordinator | Cancel |

**Who sees what** ([ADR-0015](adr/0015-privacy-first-reveal-ladder.md); rules in `shared/privacy.py`).
Every incident response has `view` (`full` or `coarse`), `location_precision`
(`exact` or `approx`) and `location_grid_km` (the grid size of a coarse
location, e.g. `1.1`; `null` when exact); hidden values are `null`.
Every view also has `summary`: the description with phone numbers, emails
and links replaced by `[number]`, `[email]`, `[link]`, at most
`PRIVACY_SUMMARY_MAX_CHARS` (default 140) characters.
The grid and the grace window are settings — see
[DATA-CONFIGURATION.md](design/DATA-CONFIGURATION.md).

| Caller | Sees |
|---|---|
| Coordinator, admin | Every request, full |
| Citizen | Own requests, full |
| Provider **not** in a verified organization | Nothing — `403` on list, nearby, detail and accept |
| Provider in a verified organization | `approved` requests: coarse (location snapped to `PRIVACY_COARSE_GRID_DEGREES`, default 0.01°; the scrubbed `summary` but no full description, rating or review). Their organization's requests: full, until `PRIVACY_ASSIGNEE_GRACE_HOURS` (default 72) after the request closes, then coarse. Never `requester_id`. Never requests still in `created` |
| Anyone except the creator, at creation | Never `tracking_token` |

Ownership rules: a citizen sees, cancels and verifies only their own
requests. `accept` needs the provider to belong to an organization, which is
recorded on the incident; only members of that organization may `start` or
`complete` it.

## Dispatch

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/dispatch/assign` | coordinator | Assign unit/person |
| POST | `/dispatch/offer` | coordinator | Offer to a resource |
| POST | `/dispatch/offers/{id}/respond` | the addressee | Accept/decline — only the person, or a member of the unit, the offer was sent to |
| POST | `/dispatch/assignments/{id}/release` | coordinator / the assignee | Release; the unit returns to `in_quarters`, the person to `available` |
| GET | `/dispatch/board` | coordinator | Three-panel feed |

## Personnel + Units

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET/PUT | `/personnel/me/status` | user | Self status |
| GET | `/personnel/statuses` | coordinator | All statuses |
| POST | `/units` | coordinator | Create unit |
| GET | `/units` | provider+ | List units |
| PUT | `/units/{id}/status` | coordinator / unit member | Change unit status |

## Organizations + Volunteers

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/organizations` | provider | Register |
| GET | `/organizations` | anon | List |
| POST | `/organizations/{id}/verify` | coordinator | Verify |
| POST | `/volunteers/enroll` | provider | Self-enroll |
| GET | `/volunteers/mine` | provider | My enrollments |
| POST | `/volunteers/{id}/approve` | coordinator | Approve |
| POST | `/volunteers/{id}/reject?reason=` | coordinator | Reject |

## Governance

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/policies` | coordinator¹ / admin | Create policy |
| GET | `/policies` | coordinator+ | List policies |
| GET | `/decisions` | coordinator+ | List decisions |
| POST | `/entity-lists` | coordinator+ | Add list entry |
| GET | `/entity-lists` | coordinator+ | List entries |

¹ A coordinator may create only an incident policy that names at least one
region (`region_scope`) and has an end time (`effective_to`). Platform-wide or
open-ended policies need an admin. Body fields: `code`, `name`, `applies_to`,
`priority`, `region_scope`, `service_types`, `priorities_allowed`,
`effective_from?`, `effective_to?`, `conditions`, `caps`.

## Files

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/files` | user | Upload to MinIO (multipart: `file`, `purpose`, `entity_type?`, `entity_id?`) |
| GET | `/files/{id}/download` | uploader, provider+ | Presigned URL |

## Messages, chat, notifications

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/messages` | coordinator+ | Send an organization message |
| POST | `/chat/channels` | provider+ | Open a channel (a provider only inside their own organization or unit) |
| GET/POST | `/chat/channels/{id}/messages` | channel member | Read / post |
| GET | `/notifications` | user | My notifications (a requester gets one when their request is approved, rejected, claimed, started, completed or cancelled; a person gets one when dispatched) |
| POST | `/notifications/{id}/read` | user | Mark one read |
| POST | `/notifications/read-all` | user | Mark all read |

## Scheduling

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/shifts` | coordinator+ | Create shift |
| GET | `/shifts` | provider+ | List shifts |
| POST | `/shifts/{id}/signup` | user | Sign up |
| POST | `/trainings` | coordinator+ | Create training |
| POST | `/trainings/{id}/assign` | coordinator+ | Assign to users |
| POST | `/calendar` | coordinator+ | Create event |

## Logistics

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/inventory/locations` | coordinator+ | Create location |
| POST | `/inventory/items` | coordinator+ | Create item |
| GET | `/inventory/items` | provider+ | List items |
| POST | `/inventory/items/{id}/transaction` | coordinator / member of the item's organization | Stock movement |

## Incident command (ICS)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST/GET | `/incidents/{id}/command` | coordinator+ / user | Establish / read command |
| POST/GET | `/incidents/{id}/lanes` | coordinator+ / user | Create / list lanes |
| POST | `/incidents/{id}/lanes/{lane_id}/assign` | coordinator+ | Assign to a lane |
| POST | `/run-logs` | coordinator+ | Open a run log |
| POST | `/run-logs/{id}/entries` | provider+ | Add an entry |

## Audit

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/audit-logs` | coordinator+ | Search the trail |

## Reports

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/reports/summary` | coordinator+ | Aggregate counts |

---

## Pagination

List endpoints return:

```json
{
  "data": [ ... ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 142,
    "total_pages": 8
  }
}
```

Query params: `?page=1&limit=20`. `limit` is clamped to 100.

The live, always-current list is the OpenAPI page at `/docs`.
