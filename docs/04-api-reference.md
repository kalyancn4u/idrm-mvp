# API Reference

Base path: `/api/v1`. All endpoints except `/health` require an
authenticated session (bearer token).

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
| POST | `/auth/register` | `{email, password, name, phone?, role?, language?}` | Create account |
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
| GET | `/users/{id}` | coordinator/admin | User detail |
| PATCH | `/users/{id}` | admin | Change role/status |

## Incidents

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/incidents` | anon or user | Create request (guest gets tracking_token) |
| GET | `/incidents` | user | List (scoped by role) |
| GET | `/incidents/mine` | citizen | My requests |
| GET | `/incidents/track/{token}` | anon | Guest tracking |
| GET | `/incidents/nearby?latitude=&longitude=&radius_km=` | provider+ | Proximity search |
| GET | `/incidents/{id}` | user | Detail |
| GET | `/incidents/{id}/updates` | user | Timeline |
| POST | `/incidents/{id}/approve` | coordinator | Approve |
| POST | `/incidents/{id}/reject` | coordinator | Reject |
| POST | `/incidents/{id}/accept` | provider | Claim — only when `approved` ([ADR-0014](adr/0014-approval-first.md)) |
| POST | `/incidents/{id}/start` | provider | Start work |
| POST | `/incidents/{id}/complete` | provider | Mark done |
| POST | `/incidents/{id}/verify` | citizen | Confirm + rate |
| POST | `/incidents/{id}/cancel` | citizen/coordinator | Cancel |

## Dispatch

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/dispatch/assign` | coordinator | Assign unit/person |
| POST | `/dispatch/offer` | coordinator | Offer to a resource |
| POST | `/dispatch/offers/{id}/respond` | provider | Accept/decline |
| POST | `/dispatch/assignments/{id}/release` | coordinator/provider | Release |
| GET | `/dispatch/board` | coordinator | Three-panel feed |

## Personnel + Units

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET/PUT | `/personnel/me/status` | provider | Self status |
| GET | `/personnel/statuses` | coordinator | All statuses |
| POST | `/units` | coordinator | Create unit |
| GET | `/units` | provider+ | List units |
| PUT | `/units/{id}/status` | provider+ | Change unit status |

## Organizations + Volunteers

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/organizations` | provider | Register |
| GET | `/organizations` | anon | List |
| POST | `/organizations/{id}/verify` | coordinator | Verify |
| POST | `/volunteers/enroll` | provider | Self-enroll |
| GET | `/volunteers/mine` | provider | My enrollments |
| POST | `/volunteers/{id}/approve` | coordinator | Approve |

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
| POST | `/files` | user | Upload to MinIO |
| GET | `/files/{id}/download` | user | Presigned URL |

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
