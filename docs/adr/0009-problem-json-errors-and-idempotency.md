# ADR 0009 — RFC 9457 problem+json errors, Idempotency-Key and optimistic versions

**Status:** Accepted.

## Context
- Clients (the UI, scripts, a future case workflow) need one error shape.
- Retries must be safe: at-least-once networks and double-clicks.
- Concurrent reviewers must not overwrite each other.

## Decision
- **Error shape:** every error is `application/problem+json` with `type`, `title`, `status`, `detail` and `instance`, plus `request_id`. Validation errors add an `errors` list. Mapping: `interfaces/api/errors.py` and LLD §12.
- **Content-addressed writes:** assessments are idempotent by content hash (201 new, 200 existing, `Location` header). Ingest is idempotent by row hash (`new_records: 0` on repeat).
- **Obligation transitions:**
  - They take `expected_version` (409 if stale) and an optional `Idempotency-Key`.
  - A replay of the same key returns the stored result with `Idempotent-Replay: true`.
  - The same key with a different request is a 409.
- **Request IDs:** every response carries `X-Request-ID` (echoed if sent), which also appears in the JSON access log.

## Consequences
- The UI and the e2e script need no special cases for errors.
- Idempotency keys are stored forever in the append-only log, which is fine at this volume.
