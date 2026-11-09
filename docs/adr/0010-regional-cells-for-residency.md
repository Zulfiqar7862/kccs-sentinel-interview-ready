# ADR 0010 — Regional cells for residency; global control plane holds no tenant evidence

**Status:** Proposed (not built in the prototype).

## Context
- `12`: some tenants have EU-only residency (T-AURA, T-NORDIA), T-VIRENT is India-only, and 14 of the other 26 tenants have residency clauses.
- Marieke de Vries (Aurastat) asked for EU residency explicitly.

## Decision
- **One cell per region** (EU, IN, AMER), each with its own Postgres, object store (WORM, 7 years), workers and log sink.
- **A thin global control plane** holds only:
  - tenant → cell routing;
  - release and config metadata;
  - the vendor bulletin feed.
- **Model routes** are per tenant: `NONE`, `EU_ENDPOINT_ZERO_RETENTION` or `ANY_ZERO_RETENTION`.

## Consequences
- **No cross-cell queries.** Platform-wide reporting uses aggregates without evidence payloads.
- **Releases** roll out cell by cell, which doubles as the canary.
- **Prototype:** one cell. The `tenant` → cell mapping is design only.
