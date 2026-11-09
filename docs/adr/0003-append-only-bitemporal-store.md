# ADR 0003 — Append-only bitemporal store

**Status:** Accepted in SQLite; Postgres Proposed.

## Context
- AUD-2603: an inspector asked for the SOP revision, stability data, series and approver behind a disposition of 14 Aug 2025. Only the outcome and the approver could be produced.
- INC-2506: a firmware bulletin learned in April changed what was true about January readings. 214 cases were affected and 61 changed.
- Two different questions must both be answerable:
  - "What did we know then?"
  - "What do we conclude now about then?"

## Decision
- Every source row is stored as a `source_record_version` with two times:
  - its **valid** meaning (dates inside the payload);
  - its **recorded_at** knowledge time.
- Corrections add a new version (`change_kind = CORRECTION`, with actor and reason). Nothing is updated or deleted.
- SQLite triggers abort any `UPDATE` or `DELETE` on all six tables in `IMMUTABLE_TABLES`: source_snapshot, source_record_version, mapping_assertion, assessment, obligation_transition, audit_event.
- Each assessment takes `valid_at` (excursion start) and `knowledge_cutoff` (`alert`, `extract`, `now` or an ISO time). It runs in one of two modes:
  - `STRICT`: only versions recorded by the cutoff.
  - `RECONSTRUCTED`: the pack has no recorded-time history, so the snapshot is a back-filled baseline, and domain knowledge dates gate further. Examples are alias `confirmed_on` and bulletin `known_from`.

## Consequences
- The at-alert replay after a correction reproduces the original assessment ID byte for byte (E9, E10).
- Readiness re-hashes every stored assessment, so tampering in the database is detected (`/health/ready`, `test_readiness_detects_a_tampered_stored_assessment`).
- The store grows forever. That is the point (7-year retention); archiving goes to a WORM object store in production.

## Alternatives rejected
- **Update in place with an audit log beside it:** the audit log becomes the real data and is never complete.
- **Snapshots only:** they cannot answer "which version did we use" for a single row.

## How we would know it was wrong
Query latency on `records(..., cutoff)` grows with history depth. Production uses Postgres with `(sheet, tenant_code, recorded_at)` indexes and partitioning by tenant.
