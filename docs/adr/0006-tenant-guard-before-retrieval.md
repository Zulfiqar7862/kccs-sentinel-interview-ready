# ADR 0006 — Tenant guard before retrieval; deny and audit

**Status:** Accepted.

## Context
- INC-2512: a Meridian case leaked into a Pinnacle draft through a shared index (Meridian Clause 22).
- GTIN 08901234500035 exists under four tenants.
- `07_Alias_Observations` has no tenant column.

## Decision
- Every read of tenant data goes through `TenantView(store, principal, tenant)`, which:
  - checks the principal's scopes;
  - writes an audit row (`TENANT_VIEW_OPEN` OK or DENIED);
  - filters by `tenant_code` in SQL.
- Caches live on the view object, so they are tenant-keyed by construction.
- Shared reference data (facilities, carriers) is readable. Untenanted **product** aliases are not readable at all.
- An unknown event in your own tenant returns 404. Another tenant's assessment returns 403 and is audited.
- The API never serves outcome columns (`ALLOWED_EVENT_FIELDS` vs `OUTCOME_FIELDS`). An AST test checks that the evidence modules never mention outcome fields.

## Consequences
- `tests/test_tenant_isolation.py` (10 tests) and API tests cover each leak path:
  - views, assessments, packages and lane history;
  - unknown identifiers;
  - stability owner taken from `tenant_code`, not the file path.
- 81 product references stay unresolved because the aliases are quarantined. That is the visible price.

## Alternatives rejected
- **Filtering after retrieval:** one missed filter is a leak.
- **Using `07` as a lookup table:** we cannot prove an alias is not Meridian-derived.

## How we would know it was wrong
A leak canary (a synthetic record unique to one tenant) shows up in another tenant's output. Production also adds Postgres row-level security as a second line.
