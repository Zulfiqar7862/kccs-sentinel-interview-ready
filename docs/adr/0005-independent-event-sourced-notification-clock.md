# ADR 0005 — Notification clock independent of disposition, stored as an event log

**Status:** Accepted.

## Context
- Board commitment #5: no notification outside its window. 14 were late in the pack.
- Kavitha's windows: 72 h, 5 days, 15 days and next business day.
- EXC-110553: a reviewer released early to meet a 72 h window that a 9-day lab test would have missed.
- INC-2502: 4 cases breached behind a storm of 1,912 alerts.

## Decision
- A separate `ObligationLedger` (domain, pure).
- One obligation per alert, created at alert receipt (`alert_ts_utc`, `00!R43`), with `due_at` computed once from the tenant's regime in `config/reference_facts.json`.
- Evidence waits are logged and **never** move `due_at`.
- `NEXT_BUSINESS_DAY` without an explicit timezone, holiday calendar and deadline time raises `PolicyIncomplete`. The obligation is kept with `due_at = null` and listed **first** with `escalate_now`. T-PINNACLE and T-MERIDIAN are affected.
- The state machine is the one in LLD §5. Only `ACKNOWLEDGED`, or `CLOSED_NOT_NOTIFIABLE` by a named human with a rationale, satisfies an obligation.
- Persistence is event sourcing: every transition is appended to `obligation_transition` (with an optimistic `expected_version` and an optional unique `idempotency_key`). The ledger is rebuilt by replaying the log at start-up and after every ingest.
- The queue is earliest-deadline-first and only shows alerts already received at `as_of`, so there is no future leakage.

## Consequences
- A restart loses nothing (`test_obligation_transitions_survive_restart`).
- A storm cannot starve another tenant's 72 h obligation (`test_storm_of_1912_synthetic_alerts_does_not_starve_other_tenants`).
- The ledger is in memory per process. Production keeps `due_at` and escalation times as columns and polls them with `FOR UPDATE SKIP LOCKED` (LLD §6).

## Alternatives rejected
- **Notification as a case state:** the case blocks on evidence, and the clock must not.
- **Treating 24 h as "next business day":** it is not the same deadline.

## How we would know it was wrong
A breach in the at-risk report with no escalation before it. The pack's own 14 late rows are re-checked by `evaluation.py`, and none is inconsistent with the kernel clock.
