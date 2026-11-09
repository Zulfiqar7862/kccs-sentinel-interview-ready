# Architecture Decision Records

Each record follows the same short template: **Context → Decision → Consequences → Alternatives rejected → How we would know it was wrong**. Status values: *Accepted* (built in the prototype), *Proposed* (production design, not built).

| # | Decision | Status |
|---|---|---|
| [0001](0001-modular-monolith-hexagonal.md) | Modular monolith per regional cell, with hexagonal layers inside | Accepted |
| [0002](0002-deterministic-kernel-no-llm-decision.md) | Deterministic evidence kernel; no language model in any decision | Accepted |
| [0003](0003-append-only-bitemporal-store.md) | Append-only bitemporal store (SQLite in the prototype, Postgres in production) | Accepted / Proposed |
| [0004](0004-content-addressed-assessments.md) | Content-addressed assessments with a code fingerprint that excludes the interfaces layer | Accepted |
| [0005](0005-independent-event-sourced-notification-clock.md) | Notification clock independent of disposition, stored as an event log | Accepted |
| [0006](0006-tenant-guard-before-retrieval.md) | Tenant guard before retrieval; deny and audit | Accepted |
| [0007](0007-abstain-on-conflict.md) | Abstain on conflict; half-open site-local date intervals | Accepted |
| [0008](0008-header-identity-prototype-oidc-production.md) | Header identity in the prototype; OIDC claims in production | Accepted / Proposed |
| [0009](0009-problem-json-errors-and-idempotency.md) | RFC 9457 problem+json errors, Idempotency-Key and optimistic versions | Accepted |
| [0010](0010-regional-cells-for-residency.md) | Regional cells for data residency; global control plane holds no tenant evidence | Proposed |
