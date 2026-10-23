# ADR-0005 — Two-App Monolith

**Status:** Accepted

## Context

The public-facing API and the staff console have different audiences, different
renderers (JSON vs HTML), and different deployment profiles. But they operate
on **the same data**.

## Decision

Deploy **two peer applications in one repository**, sharing the `shared/`
package:

- `app/` — FastAPI JSON API
- `dashboard/` — Flask HTML console

They never import each other. A `make lint` rule enforces this.

## Consequences

- Each app can be deployed independently.
- Code in `shared/` is imported by both.
- Both apps write to `audit_logs` with the same shape.
- A future micro-service split is possible without a rewrite.

