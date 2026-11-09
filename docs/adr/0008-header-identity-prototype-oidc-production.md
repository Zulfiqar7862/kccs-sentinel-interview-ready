# ADR 0008 — Header identity in the prototype; OIDC claims in production

**Status:** Accepted (prototype); Proposed (production).

## Context
The prototype must show authorisation decisions (tenant scope, roles, audit) without an identity provider.

## Decision
- **Prototype headers:** `X-Actor`, `X-Tenant-Scope` (comma list) and `X-Roles`. Roles are QA_REVIEWER, QA_DATA_STEWARD, REGULATORY_AFFAIRS and PLATFORM_ADMIN.
- **Missing or malformed identity:**
  - Missing headers return 401.
  - Malformed values return 422.
  - A missing role returns 403.
- **Role-gated actions:**

  | Action | Role |
  |---|---|
  | Ingest | PLATFORM_ADMIN, with the path inside `KCCS_DATA_DIR` |
  | Corrections | QA_DATA_STEWARD |
  | Obligation transitions | REGULATORY_AFFAIRS |

- **Production:** the same `Principal` object is built from verified OIDC token claims (tenant scopes and roles) at the gateway, and the headers are dropped.

## Consequences
- The prototype **must not** be exposed beyond localhost, since anyone can send headers. The default bind is `127.0.0.1`; Docker binds `0.0.0.0` inside the container only.
- `/api/v1/system/info` is unauthenticated and lists tenant codes. That is acceptable for a demo, not for production.

## How we would know it was wrong
Any deployment outside a laptop or a private network without the OIDC change. That is a release blocker in the production checklist.
