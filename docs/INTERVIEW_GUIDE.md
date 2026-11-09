# Interview guide

Plain-English notes for the 90-minute conversation: 20 minutes of walkthrough, two deep dives, and 20 minutes on an unseen change. Every number here comes from running the code (`scripts/e2e_check.sh`, results in `evidence/`). If you are asked about a number that is not here, say "I'd have to run it", not a guess.

---

## 0. Numbers cheat sheet (all verified by the e2e run)

| Fact | Value | Source |
|---|---|---|
| Events in the pack | 420 across 8 tenants (T-VIRENT 164, T-SAHYADRI 83, T-KAVERI 44, T-AURA 33, T-NORDIA 28, T-PINNACLE 26, T-CAMPOS 26, T-MERIDIAN 16) | workbook tab 01 |
| Rows ingested | 1,413; re-ingest adds 0 | E6, E7 |
| Assessments in the demo | 841 = 420 × 2 cutoffs + 1 after a correction | E11 |
| Status of all 420 | `ABSTAIN_BLOCKING_EVIDENCE_GAPS`. At alert, 8 have only pack-wide gaps (no series, no SOP content) | `evaluation_summary.md` |
| Top blocking reason | `NO_SOP_INDEXED` 164: all of T-VIRENT has no excursion SOP in the index | same |
| Engine AUTO_CLOSE rows with case-specific evidence gaps | 273 of 275 | same |
| 24 override reasons | 13 surfaced, 1 only generically, 1 not surfaced (EXC-110476), 6 out of scope (data not in pack), 1 prevented by construction, 1 authority field, 1 notification track | same |
| Firmware TT-2.14.3 | 91 events; 19 flagged at alert, 91 at extract; 61 historically reopened | same |
| Late notifications in the pack | 14. None is inconsistent with the kernel clock; 9 are next-business-day rows the kernel refuses to compute | same |
| EXC-107133 at alert | `ASM-ac3e4e7b0db4567a09c245ad` | E19, E32 |
| EXC-107133 at extract | `ASM-9be5fe90a6a927d0887e37b5` (supersedes the first) | E34 |
| EXC-107133 deadline | 2026-08-12T06:31:00Z (360 h from the alert at 06:31Z, not from 06:14) | E18, E40 |
| Tests | 131 passed with the workbook | E3 |
| e2e checks | 47 of 47 pass | `evidence/RESULT.txt` |

Assessment IDs depend on the code fingerprint. If you change any rule file, the IDs change. That is on purpose ([ADR 0004](adr/0004-content-addressed-assessments.md)). Re-run `make e2e` before the interview and quote what it prints.

---

## 1. The 5-minute pitch

> "Kestrel doesn't have a decision problem. It has an evidence problem. The brief says it directly: 'the decisions are mostly not hard; assembling enough evidence to be allowed to make them is the whole cost.' The pack agrees. Most of the 24 override reasons are about evidence: the wrong SOP revision, the wrong study presentation, the wrong carrier entity. All six incidents are failures of version control, evidence or tenant isolation, not of judgement.
>
> So I built the part that keeps me up at night: an **evidence kernel**. For any alert, it builds a basis that is:
> - **tenant-scoped**: GTIN 08901234500035 exists under four tenants, and identity is always (tenant, identifier);
> - **explicit about time**: which SOP revision was in force at *that site* on *that local date*, and what we knew at a given moment;
> - **reproducible**: the assessment ID is a hash of its content, including the code and the rules.
>
> It never decides. Where the evidence conflicts, it **abstains** and names the human action. Look at EXC-107133, the brief's own case. Two SOP revisions overlap. The product master points to a vial study for a pen. The right pen study exists but isn't referenced. The kernel shows all of that in under a second, with row references.
>
> Separately, it runs the **regulatory notification clock** from alert receipt. Waiting for evidence never pauses it, and a next-business-day rule without a calendar is escalated, not guessed.
>
> Every result can be exported as a hashed package, and a tampered package fails verification. That's board commitment #3 and the Aurastat inspection.
>
> No language model is involved in any decision. That satisfies Dr Rao's condition, avoids a repeat of the November prompt incident, works for the six API-prohibited tenants, and costs $0 on a quiet Sunday.
>
> I'd start with **one customer, T-KAVERI**, because the board minute says 'one customer and certain'. And I challenge one target: '70% closed without a person' must mean 70% *safely* closed, audited, because 273 of 275 auto-closures in the pack had evidence gaps."

---

## 2. The 20-minute walkthrough (script with timings)

| Min | What you say | What you show |
|---|---|---|
| 0–2 | The real problem (pitch, short version). Four things kept separate: closure, disposition, notification, liability | `docs/01_where_we_land.md` §1 |
| 2–5 | Requirements → decisions. Pick 4 rows from the traceability table: R3 SOP in force, R5 no later knowledge, R7 independent clock, R10 no cross-tenant artefacts | `01` §2 |
| 5–8 | Architecture. Context diagram, then the cell model for residency, then the hexagonal layers inside one process | HLD §A1, §A2, §A3 |
| 8–14 | **Live demo** (section 3 below). EXC-107133 end to end | browser at `/ui/` |
| 14–16 | How I know it works: 131 tests, 47 e2e checks, replay over 420 events against the 24 override reasons, and the one I *didn't* catch (EXC-110476) | `evidence/`, `evaluation_summary.md` |
| 16–18 | The 3 a.m. question: readiness re-hashes stored assessments, metrics, and a proposed nightly replay canary | HLD §A9 |
| 18–20 | Rollout: Kaveri first, gates G0/G1, rollback by flag. What I deliberately did not build | `01` §3, §6 |

**Tip:** the brief says "a short submission that draws its own boundary is a strong one." Say clearly what you did **not** build: the case workflow, the closure policy, connectors and the precedent search. They are designed, not built, and each is marked [DESIGN].

---

## 3. Demo steps (exact commands)

### 3.1 Before the interview (once)

```bash
git clone <repo> && cd kccs-adjudication-case-study
git checkout improve/interview-ready
mkdir -p data && cp /path/to/KCCS_Sentinel_Reference_Data_Pack.xlsx data/
make check          # ruff + mypy + 131 tests
make e2e            # 47 checks, refreshes evidence/ (about 30 s)
```

### 3.2 Start the demo (one command)

```bash
make demo           # runs the CLI demo into artifacts/, then serves http://127.0.0.1:8000/ui/
# or, with Docker:
docker compose up --build    # http://localhost:8000/ui/
```

`make demo` uses a fixed clock (`2026-11-08T12:00:00Z`) so the IDs match the documents.

### 3.3 Clicks in the UI (8 minutes)

1. **Cases tab**. Click the link **EXC-107133 (T-KAVERI)** (the brief's case).
   - Point out that the event list shows no outcome columns. The kernel never sees what the reviewer decided.
2. Choose **As known at alert time**, then click **Assess**. Walk through the cards:
   - **Status:** `ABSTAIN_BLOCKING_EVIDENCE_GAPS`, `is_disposition: false`.
   - **Entities:** GTIN → `02_Product_Master!R57`. "Bhiwandi Hub" → BOM-NX-04. "Tapti Exp Cargo" → CNT-2021-0245, which has no cold-chain clause. That affects who pays, not what happens to the product.
   - **SOP:** SOP-KAV-9392, **Rev 02 and Rev 03 both in force** on 2026-07-28. We do not pick one.
   - **Stability:** STB-3584 rejected for three stated reasons (vial vs pen, partly readable, accelerated). STB-2738, the pen study, is admissible but only a candidate. The master says "cumulative 72 h"; the study says "one excursion ≤ 6 h below 15 °C". That is a conflict.
   - **Regulatory clock:** due 2026-08-12T06:31Z, from the alert time, not the excursion start.
   - **Manifest:** code hash, rule hashes, 8 cited source versions, `model: NONE`.
3. Choose **As known at pack extract (2026-09-14)**, then click **Assess**. You get a new ID, and **Assessment history** shows `supersedes`.
   - "Same event, later knowledge, a different and linked record. The first one is unchanged."
4. **Export evidence package**, then **Verify package** (OK), then **Tamper with a copy**.
   - The tampered copy fails with `hash mismatch assessment.json`.
5. **Try reading this as another tenant**: 403, and a DENIED row appears in the **Audit trail** tab.
6. **Notification clock tab**. Set as-of `2026-07-29T12:00:00Z` and tick *all tenants in my scope*.
   - It is earliest deadline first, and it shows only alerts already received by the as-of time (the last 168 h).
   - Verified result: 8 rows. **EXC-110658 (T-MERIDIAN, next business day) is first with "escalate now"**, because its deadline cannot be computed without a calendar.
   - Next is **EXC-110693 (T-AURA)**, already breached (due 2026-07-26). It is one of the pack's 14 late notifications, and the queue shows it rather than hiding it.
   - EXC-107133 has 330.5 h left.
   - Move one obligation to `NOTIFIABLE_CONFIRMED`. The queue reloads with version 2.
   - To show the 409 for a stale version, use the stale-version curl in 3.4.
7. **System tab**: readiness (integrity self-check), versions and config hashes.

### 3.4 Same thing with curl (if the browser fails)

```bash
B=http://127.0.0.1:8000; H=(-H "X-Actor: demo-qa" -H "X-Tenant-Scope: T-KAVERI")
curl -s $B/health/ready
curl -s "${H[@]}" -H 'Content-Type: application/json' -d '{"knowledge_cutoff":"alert"}' \
     $B/api/v1/tenants/T-KAVERI/events/EXC-107133/assessments | python3 -m json.tool | head -40
curl -s "${H[@]}" $B/api/v1/tenants/T-AURA/events                      # 403 problem+json
curl -s "${H[@]}" -X POST $B/api/v1/assessments/ASM-ac3e4e7b0db4567a09c245ad/package
curl -s "${H[@]}" $B/api/v1/assessments/ASM-ac3e4e7b0db4567a09c245ad/package/verify
curl -s "${H[@]}" "$B/api/v1/obligations/queue?as_of=2026-07-29T12:00:00Z&only_at_risk=false&received_within_hours=168"
curl -s "${H[@]}" -H "X-Roles: REGULATORY_AFFAIRS" -H 'Content-Type: application/json' -H 'Idempotency-Key: demo-1' \
     -d '{"to_state":"NOTIFIABLE_CONFIRMED","expected_version":1,"note":"demo"}' \
     $B/api/v1/tenants/T-KAVERI/obligations/EXC-107133/transitions        # applied, version 2
# same call, same key again -> 200 with header Idempotent-Replay: true (safe retry)
# same body with a NEW key (or no key) -> 409: expected_version 1 is stale
curl -s -o /dev/null -w '%{http_code}\n' "${H[@]}" -H "X-Roles: REGULATORY_AFFAIRS" -H 'Content-Type: application/json' \
     -d '{"to_state":"SUBMISSION_QUEUED","expected_version":1,"note":"stale"}' \
     $B/api/v1/tenants/T-KAVERI/obligations/EXC-107133/transitions
curl -s $B/metrics
```

OpenAPI: `http://127.0.0.1:8000/docs`.

---

## 4. Likely questions and short answers

### HLD

- **Why a modular monolith, not microservices?**
  - About 11,400 alerts a month, a team of six, and work that is transactional and heavy on audit.
  - Microservices would add distributed consistency problems and cross-service tenant checks, with no scaling need behind them.
  - Layers are enforced by an import test ([ADR 0001](adr/0001-modular-monolith-hexagonal.md)).
- **How do you meet EU residency?**
  - Regional cells. Each has its own database, object store and logs.
  - The global control plane holds only routing and release metadata ([ADR 0010](adr/0010-regional-cells-for-residency.md)).
  - This is design only in the prototype.
- **What happens when Docuvault or telemetry is down?**
  - We use only versions recorded before the cutoff; otherwise we abstain.
  - The notification clock is never affected (HLD Part B §4).
- **What happens in a storm like February's?**
  - One obligation per alert, earliest deadline first, per-tenant queues.
  - Storm grouping is for display only.
  - A test with 1,912 synthetic alerts shows another tenant's 72 h obligation stays first.
- **Cost? A quiet Sunday?**
  - The kernel uses no model, so $0 model spend.
  - The optional drafting design is about $553–575 a month of the $2,939 ceiling.
  - On a quiet Sunday only the always-on app tier runs, and that is a capital line.
  - Self-hosting for API-prohibited tenants costs $4,139 a month for one GPU, which is more than the whole budget. That is why "no LLM" is a supported route (HLD Part B §9).

### LLD

- **How do you pick the SOP revision?**
  - Half-open site-local dates: `from <= d < to`. There are 115 hand-overs where `to == next from`, so closed intervals would create 115 false overlaps.
  - If the site's timezone is untrusted, we check every plausible local date.
  - Two revisions in force means a conflict, never "highest revision wins". SOP-MER-5228 Rev 05 comes before Rev 04 in time.
- **What is a knowledge cutoff?**
  - It answers "what did we know at time X". Reads return only versions with `recorded_at <= X`.
  - The pack has no recorded-time history, so RECONSTRUCTED mode uses the knowledge dates the pack does have: alias `confirmed_on`, bulletin `known_from`.
  - It says so in every assessment.
- **How is an assessment ID built?**
  - sha256 of the canonical JSON payload, which includes the manifest (code hash, rule hashes, cited row versions).
  - Same inputs give the same ID; any change gives a new ID that links to the old one.
- **What is the obligation state machine?** See LLD §5 and §13.
  - Only ACKNOWLEDGED, or a named human's NOT_NOTIFIABLE with a reason, satisfies an obligation.
  - Every move needs the current version, otherwise 409.
  - It is stored as an append-only event log and rebuilt on start.
- **How do you stop concurrent edits?**
  - `expected_version` gives optimistic locking (409).
  - `Idempotency-Key` makes retries safe, and reusing a key for a different request is a 409.
- **Errors?** Always RFC 9457 problem+json with a `request_id` (LLD §12).

### Trade-offs

- **"Everything abstains. Isn't that useless?"**
  - No. It tells the reviewer exactly what is missing, with row references, instead of 1 h 50 min across seven systems.
  - The blocking reasons are the curation backlog: T-VIRENT needs its excursion SOP indexed, and 116 events have a master-vs-study conflict to resolve.
  - A green status is only possible when the evidence exists. I will not fake it.
- **Why not fuzzy matching for products?**
  - That is exactly how the wrong presentation gets picked (vial vs pen).
  - Mappings are human-approved and versioned.
- **Why are product aliases in tab 07 quarantined?**
  - They have no tenant column, so we cannot prove an alias is not Meridian-derived (Clause 22).
  - The cost is 81 unresolved product refs. I show that number rather than hide it.

### Scaling

- **The prototype uses SQLite with a single lock.** Production uses Postgres per cell, behind the same `EvidenceStore` port.
  - Stateless API replicas, with workers using `FOR UPDATE SKIP LOCKED`.
  - Tables partitioned by tenant, plus row-level security.
- **Telemetry at 10 M readings a day:** a separate ingest worker and a columnar store. Snapshot only the evidence window per alert, because SYS-01 keeps raw data for 30 days only.
- **The real bottleneck is people:** SOP, study and mapping curation per tenant. That is why I commit to *onboarding* all 34 tenants in 9 months, not to equal maturity.

### "Why no LLM in the decision?"

- Dr Rao: "If the conclusion is right and the reasoning was invented, that is worse than useless."
- November: a prompt change moved 31 customers. June: a model sunset.
- The January pilot cited studies that do not exist.
- The hard part is evidence assembly, which is deterministic.
- A model may later *draft prose from the assessment JSON*. It never decides, and it can be removed with no loss of function ([ADR 0002](adr/0002-deterministic-kernel-no-llm-decision.md)).

### Testing

- 131 tests:
  - unit tests on real workbook rows (each named after the event);
  - synthetic fixtures only for what the pack lacks (storm, product ambiguity), clearly labelled;
  - API contract tests that need no workbook;
  - architecture tests;
  - one test per reviewer question.
- 47 e2e checks on a fresh venv: install, lint, types, tests, CLI, the API with every endpoint, and the UI being served.
- **Tests that catch my own mistakes:**
  - an AST test that the evidence code never mentions outcome fields;
  - a test that the assessment ID is independent of the actor;
  - a test that a correction leaves the old assessment byte-identical.
- **Honest misses:** EXC-110476 is NOT_SURFACED (two master rows / wrong spec), and EXC-110602 is surfaced only generically.

### "How would you know it broke at 3 a.m. in six months?"

1. `/health/ready` goes to 503 if the append-only triggers are missing or any stored assessment's hash no longer matches. The orchestrator stops sending traffic.
2. `/metrics` has `kccs_ready`, `kccs_assessments_failing_hash` and the 5xx rate. Page on these.
3. Proposed: a **nightly replay canary**. Re-assess 50 frozen past alerts and compare the IDs. A change with no release means something changed underneath.
4. Proposed: **reconcile obligations against the source alert count** per tenant per hour. A missing obligation is the one silent failure.

---

## 5. The unseen change (last 20 minutes): how to absorb it

Use the same five steps for any change:

1. **Where does it live?** Config (rules, regimes, tenant policy), domain rule, adapter, or a new port.
2. **What version does it get?** Config is hashed into the manifest; code is fingerprinted.
3. **Replay before shipping.** Re-run the evaluation for every tenant, diff IDs and findings, and name every tenant whose diff is not empty. That is Dr Rao's condition.
4. **What happens to the past?** Nothing is edited. New knowledge gives new assessments that `supersede` the old ones, and reopen candidates. The at-alert replay still gives the old ID.
5. **Does the notification clock change?** Usually not. If a regime changes, existing `due_at` values stay as they were registered, and new alerts use the new regime version.

**Worked examples:**

| Change they might give you | How the design absorbs it |
|---|---|
| "Brazil changes 5 days to 3 days" | Edit `notification_regimes` in `config/reference_facts.json` (new version + hash). New alerts get 72 h. Replay shows exactly which T-CAMPOS events would change their deadline. Old obligations keep the deadline they were registered with, with the regime version recorded |
| "A new firmware bulletin, known from today" | Add it to `firmware_bulletins` with `known_from`. At-alert replays are unchanged; at-now assessments add `FIRMWARE_BULLETIN_APPLIES` and the reopen recommendation (as INC-2506: 91 events, 19 → 91) |
| "QA says Rev 03 governs at Bhiwandi" | `POST /tenants/T-KAVERI/corrections` on `05_SOP_Index` (QA_DATA_STEWARD). A new version is recorded with actor and reason. Re-assess at `now` gives a new ID without SOP_REVISION_OVERLAP; at `alert` the old ID is unchanged (E9, E10) |
| "A new customer with EU residency and no model APIs" | Tenant policy row: cell = EU, model route = NONE, signer rule. No code fork |
| "A new data source (carrier setpoint CSV)" | New adapter in `infrastructure/`, ingested as `source_record_version` with its own sheet name; a new signal in `domain/signals.py`; a new finding code. The replay diff shows the impact |
| "Let a model write the justification" | An optional drafting step after the assessment, input = assessment JSON only, per-tenant route, template fallback. It never changes status or findings |
| "We now have the raw temperature series" | Implement the telemetry archive stub; `TEMPERATURE_SERIES_NOT_AVAILABLE` stops blocking; `readings_in_window` checks become real. The replay shows how many events lose that blocker |

---

## 6. Code tour (file → what it does)

| Open this | To show |
|---|---|
| `src/kccs_evidence/domain/policy_sop.py` | SOP selection; overlaps become conflicts |
| `src/kccs_evidence/domain/temporal.py` | Half-open intervals; plausible local dates for untrusted timezones |
| `src/kccs_evidence/domain/stability.py` | Study admissibility and stated rejection reasons |
| `src/kccs_evidence/domain/signals.py` | Firmware band as an interval; telemetry gap findings |
| `src/kccs_evidence/domain/obligations.py` | Notification clock and state machine (pure) |
| `src/kccs_evidence/application/access.py` | `TenantView`: scope check and audit **before** any read |
| `src/kccs_evidence/application/assessment.py` | Builds the assessment, manifest, code fingerprint; supersession |
| `src/kccs_evidence/application/package.py` | Evidence package export / verify |
| `src/kccs_evidence/application/evaluation.py` | Replay over history (Dr Rao's condition) |
| `src/kccs_evidence/application/service.py` | Facade for the CLI/API; obligation log replay; idempotency |
| `src/kccs_evidence/infrastructure/sqlite_store.py` | Schema, append-only triggers, bitemporal reads, integrity check |
| `src/kccs_evidence/interfaces/api/` | FastAPI app, problem+json errors, identity headers, routers |
| `src/kccs_evidence/config/*.json` | Rules as data: scope rules, regimes, bulletins, tenant constraints |
| `tests/test_architecture.py` | Layers can only depend inwards |
| `tests/test_reviewer_questions.py` | One test per reviewer question |

---

## 7. Limitations to state before they find them

- **Identity is by header** (`X-Actor`, `X-Tenant-Scope`, `X-Roles`), not OIDC. Never expose the prototype beyond localhost ([ADR 0008](adr/0008-header-identity-prototype-oidc-production.md)).
- `/api/v1/system/info` is unauthenticated and lists tenant codes.
- **SQLite with one lock:** a single writer. Fine for a demo, not for production.
- **The obligation ledger is rebuilt in memory** from the event log. Production keeps it in Postgres with durable timers.
- **Not built:** case workflow, signatures, the closure policy, connectors, the precedent store and regulator submission ([DESIGN] in the docs).
- **Missing from the pack:** the raw temperature series, SOP annexure content and batch IDs. Those findings are blocking by design.
- An unknown key maps to 404 through a generic `KeyError` handler. That is coarse, but it never reveals other tenants.
- **Docker** was verified in a sandbox that needed host networking for the build. The compose file itself is standard.
- **CI** is defined (`.github/workflows/ci.yml`) but was not run on GitHub from this environment.
