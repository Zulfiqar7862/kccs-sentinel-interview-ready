# ADR 0001 — Modular monolith per regional cell, with hexagonal layers inside

**Status:** Accepted (layers built and enforced by tests); cells Proposed.

## Context
- The work is transactional and audit-heavy, with moderate volume: about 11,400 alerts and 2,050 reviewed cases a month (`13`), and bursts of 1,912 alerts in 38 minutes (INC-2502).
- A team of six has to build it and run it.
- The rules that matter (which SOP revision, which study, which deadline) must be testable with no database, web framework or network.

## Decision
- One deployable application per regional cell, with background workers for slow work.
- Inside it, four layers that may only depend inwards:
  `domain` (pure rules and ports) ← `application` (use cases, tenant guard, service facade) ← `infrastructure` (SQLite store, workbook reader) ← `interfaces` (CLI, REST API, web UI).
- `config/` holds the versioned rule data and is hashed into every assessment.
- `tests/test_architecture.py` parses every module's imports (AST) and fails the build if:
  - a layer imports outwards;
  - `domain` or `application` import FastAPI, Starlette, pydantic, uvicorn, sqlite3 or openpyxl.

## Consequences
- The kernel is the same code under the CLI, the API, Docker and the tests. The EXC-107133 assessment ID is identical across all of them (see `evidence/results/checks.tsv`, E19 and E32).
- Swapping SQLite for Postgres means writing one new adapter for the `EvidenceStore` port (`application/ports.py`). No rule changes.
- One process, so there are no distributed transactions. Scaling is per cell (see HLD §Scalability).

## Alternatives rejected
- **Microservices per capability:** cross-service tenant checks and an outbox on every hop, with no scaling need to pay for them.
- **One flat package (the original layout):** it worked, but nothing stopped the rules from importing the database or the web layer.

## How we would know it was wrong
Two signs: one module needs a different scaling profile, such as telemetry ingest at 10 M readings a day; or teams block each other on releases. The first is already expected: ingest is drawn as a separate worker.
