# Use-case coverage matrix

This table maps **every requirement in the brief** to the code, the API endpoint and the tests or e2e checks that prove it. It covers:
- the four deliverables;
- the six board commitments and two conditions;
- the six incidents;
- the twelve reviewer questions (tab 10);
- what each stakeholder said.

Status:
- **IMPL**: built and tested.
- **PARTIAL**: built, but limited by the pack's data.
- **DESIGN**: documented, not built.
- **OUT**: deliberately not done, with the reason.

Conventions:
- Paths are relative to `src/kccs_evidence/`.
- Tests are in `tests/`.
- `E##` are the checks in `scripts/e2e_check.sh`, with results in `evidence/results/checks.tsv`.
- Endpoints are under `/api/v1` unless shown otherwise.

## 1. Brief deliverables (§8)

| Deliverable | Where it is | Status |
|---|---|---|
| A. Where you land | `docs/01_where_we_land.md` (problem statement, requirements R1–R16, non-goals, positions on contradictions, board targets challenged, phased rollout) | IMPL |
| B. Design (HLD + LLD) | `docs/02_architecture_hld.md`, `docs/03_detailed_design_lld.md`, `docs/adr/` | IMPL |
| C. Something running: the hardest part | The evidence kernel: tenant-scoped, time-explicit, reproducible basis, plus the independent notification clock. It runs as the CLI, the REST API and the web UI; e2e has 47 checks | IMPL |
| C. "How you know it works" | 131 tests, ruff, mypy, e2e (`evidence/`), replay evaluation against the 24 override reasons (`application/evaluation.py`) | IMPL |
| C. "How you'd know at 3 a.m. in six months" | `/health/ready` integrity self-check, `/metrics`, JSON logs with `request_id`; HLD §A9 | IMPL (alert rules DESIGN) |
| D. Working log of AI use | `docs/06_working_log.md` | IMPL |

## 2. Board commitments and conditions (§6)

| # | Commitment | What the system does | Code | API | Tests / checks | Status |
|---|---|---|---|---|---|---|
| 1 | Median alert → signed disposition < 24 h | Removes the look-up cost by assembling evidence before a human opens the case; names exactly what is blocking. We challenge "median" and report p50/p90/max per wait state (`01` §7) | `application/assessment.py` | `POST /tenants/{t}/events/{e}/assessments` | `test_brief_case_assessment_is_idempotent_and_abstains`, E13–E18, E31 | PARTIAL (latency is human-bound; case workflow is DESIGN) |
| 2 | ≥ 70% closed without a person | The kernel **never** closes or decides. It shows that 273 of the 275 engine AUTO_CLOSE rows had case-specific evidence gaps, which is a reason to audit closures, not to automate more | `application/evaluation.py` | — (CLI `demo`) | `evidence/results/evaluation_summary.md` | DESIGN (closure policy); evidence IMPL |
| 3 | Full basis within the hour, for 7 years | Content-addressed assessment + manifest + hashed evidence package; append-only store | `application/package.py`, `infrastructure/sqlite_store.py` | `POST /assessments/{id}/package`, `GET .../package/verify`, `GET .../package.zip` | `test_export_and_verify`, `test_tampering_detected`, `test_package_is_reproducible`, `test_package_export_verify_zip_and_tamper_detection`, E12, E22, E24, E37–E39 | IMPL (WORM storage DESIGN) |
| 4 | Inside the cost ceiling (tab 13) | No model in the kernel: $0 per assessment; manifest says `model: NONE`. Cost model in HLD Part B §9 | `application/assessment.py` (manifest) | `GET /system/info` (`model.route`) | `test_metrics_and_system_info` | IMPL (kernel); DESIGN (optional drafting) |
| 5 | No notification outside its window | Independent clock from alert receipt; EDF queue; policy-incomplete regimes escalated first; transitions persisted | `domain/obligations.py`, `application/service.py` | `GET /obligations/queue`, `GET /tenants/{t}/obligations`, `POST /tenants/{t}/obligations/{e}/transitions` | `tests/test_obligations.py` (9), `test_obligation_queue_orders_by_deadline_and_escalates_incomplete_policy`, `test_obligation_state_machine_guards`, `test_obligation_transitions_survive_restart`, `test_obligation_queue_never_shows_alerts_received_after_as_of`, E18, E40–E43 | IMPL (regulator transport DESIGN) |
| 6 | First customer in 90 days; all 34 in 9 months | T-KAVERI first (`01` §6). Per-tenant config is data (`config/reference_facts.json`), not forks | `config/` | — | — | DESIGN (plan) |
| C1 | **Dr Rao:** replay on past cases, show where it would decide differently and why, before every change | Replay over all 420 events, at two knowledge cutoffs, compared with the historical engine output and the 24 written override reasons. Content IDs make any behaviour change visible | `application/evaluation.py`, `application/demo.py` | — (CLI `demo`, `make demo`) | `evaluation_summary.md`: 13 SURFACED, 1 generic, 1 NOT_SURFACED, 6 OUT_OF_SCOPE, 1 prevented by construction, 1 authority field, 1 notification track | IMPL |
| C1 | Automation on closures only, never on decisions | `is_disposition` is always false; statuses are only READY_FOR_QA_REVIEW or ABSTAIN | `application/assessment.py` | every assessment | `test_never_a_disposition_across_all_events`, `test_outcome_fields_are_not_inputs` | IMPL |
| C2 | "One customer and certain" | Abstain on conflict; T-KAVERI first; feature flag rollback (`01` §6) | `domain/policy_sop.py`, `domain/stability.py` | — | `tests/test_temporal.py` | IMPL / DESIGN |

## 3. Incidents (§3, tab 14)

| Incident | Requirement it creates | Code | API | Tests / checks | Status |
|---|---|---|---|---|---|
| **INC-2411** prompt change moved 31 customers | Every behaviour-affecting artefact is versioned and hashed; a change shows up as new IDs per tenant | `application/assessment.py` (`code_fingerprint`, manifest), `config/loader.py` | `GET /system/info` (`code_sha256`, config hashes) | `test_fingerprint_excludes_interfaces_but_covers_rules`, `test_repeated_execution_is_idempotent`, E19, E32 | IMPL (replay gate in CI DESIGN) |
| **INC-2502** storm of 1,912 in 38 min; 4 breached | One obligation per alert; earliest deadline first; other tenants not starved | `domain/obligations.py` | `GET /obligations/queue` | `test_storm_of_1912_synthetic_alerts_does_not_starve_other_tenants`, `test_storm_keeps_every_obligation_real_inc_2502_rows` | IMPL |
| **AUD-2603** could not produce the SOP revision, stability data, series and approver | Reconstruct the basis for any past date, as known then | `application/assessment.py` (time semantics), `application/package.py` | assess with `knowledge_cutoff`, package export | `test_replay_excludes_bulletin_learned_after_alert`, `test_correction_produces_new_assessment_and_old_is_immutable`, E9, E10; `TEMPERATURE_SERIES_NOT_AVAILABLE` is blocking because the series is not in the pack | IMPL (series archive DESIGN) |
| **INC-2506** firmware under-reported up to 1.8 °C; 214 affected, 61 changed | Firmware as an interval; bulletins gated by `known_from`; reassessment proposes reopen, never edits the original | `domain/signals.py` (`firmware_uncertainty`), `application/assessment.py` | assess at `extract` vs `alert` | `test_firmware_up_to_1_8_is_an_interval_not_a_fixed_offset`, `test_exc_110448_cold_excursion_with_affected_firmware`, `test_bulletin_reassessment_recommends_reopen_without_editing_original`; summary: 91 TT-2.14.3 events, 19 flagged at alert, 91 at extract | IMPL |
| **INC-2509** model sunset | No model in the kernel, so nothing to re-qualify | manifest `model.route = NONE` | `GET /system/info` | `test_metrics_and_system_info` | IMPL |
| **INC-2512** Meridian case in a Pinnacle draft (Cl.22) | Tenant guard before retrieval; tenant-filtered lane history; no untenanted product aliases | `application/access.py` | every tenant route → 403 + audit | `tests/test_tenant_isolation.py` (10), `test_cross_tenant_reads_are_denied_and_audited`, E8, E21, E23, E35, E36 | IMPL |

## 4. The twelve reviewer questions (tab 10)

| Q | Question (short) | Kernel answer | Code | Tests | Status |
|---|---|---|---|---|---|
| 1 | Which SOP revision was in force at origin / destination on the date? | `evidence.sop_origin`, `sop_destination`: SELECTED / CONFLICT / NONE_IN_FORCE / BOUNDARY_AMBIGUOUS | `domain/policy_sop.py`, `domain/temporal.py` | `test_q1_…`, `test_real_overlap_exc_107133`, `test_half_open_boundary_in_site_local_date`, `test_untrusted_timezone_near_boundary_is_ambiguous_not_guessed` | IMPL (annexure content DESIGN) |
| 2 | What does the stability data permit, cumulatively? | Admissible study or a stated rejection; master vs study conflict; cumulative marked unverifiable | `domain/stability.py`, `domain/signals.py` | `test_exc_107133_…`, `test_exc_110497_…`, `test_cumulative_allowance_never_reported_as_satisfied`, `test_q2_refer_qa_…`, `test_q2_freeze_…` | IMPL |
| 3 | Anything on this lane / carrier in 90 days? | `LANE_HISTORY_PRESENT`, same tenant only, knowledge-gated | `application/assessment.py` (`_lane_history`) | `test_q3_…`, `test_lane_history_never_includes_other_tenants` | IMPL |
| 4 | Parent or subsidiary contract, and what clause? | Carrier legal entity per leg → contract; no cold-chain clause = liability finding | `domain/resolution.py` (`resolve_carrier`), `_liability` | `test_q4_…` (2) | IMPL |
| 5 | Did the gateway gap overlap the excursion? Interpolated? | `GATEWAY_GAP_IN_WINDOW`, `INTERPOLATED_READINGS`, `GATEWAY_GAP_SPANS_EXCURSION` (blocking) | `domain/signals.py` (`telemetry_findings`) | `test_q5_…` | IMPL (from aggregates; the raw series is not in the pack) |
| 6 | Same physical excursion under another ID? | Not answered: the pack has no physical excursion key | — | `test_q6_…` asserts nothing claims it | OUT |
| 7 | Was product in the room when the equipment alarmed? | `BMS_TENANT_ATTRIBUTION_DERIVED`, `DOCK_DOOR_ALIGNMENT_UNVERIFIED`; conflicting attribution quarantined | `domain/signals.py`, `application/assessment.py` | `test_q7_…` (2), `test_conflicting_tenant_attribution_is_quarantined` | PARTIAL |
| 8 | Earlier excursion on this batch; cumulative past limit? | `BATCH_EXPOSURE_HISTORY_UNAVAILABLE` (no batch IDs in the pack) | `application/assessment.py` | `test_q8_…`, `test_cumulative_allowance_never_reported_as_satisfied` | PARTIAL |
| 9 | Who signs; second signature? | `disposition_authority` from tab 12 (who signs, dual, language, residency, model APIs) | `application/assessment.py`, `config/reference_facts.json` | `test_q9_…` | IMPL (enforcement DESIGN) |
| 10 | Reportable, where, by when? | `notification_track` + obligation; notifiability stays a human decision | `domain/obligations.py` | `test_q10_…`, `tests/test_obligations.py` | IMPL |
| 11 | What did we decide last time, and why? | Same-tenant lane history with knowledge gate; reasoning store (Deepa's spreadsheet) as a tenant-scoped precedent store | `_lane_history` | `test_lane_history_never_includes_other_tenants` | PARTIAL (precedent reasoning DESIGN) |
| 12 | Can I reconstruct all this in two years? | Manifest + cited versions + package + append-only store + replay at any cutoff | `application/package.py`, `infrastructure/sqlite_store.py` | `test_q12_…`, `test_append_only_tables_reject_update_and_delete`, E9, E10, E12 | IMPL |

## 5. Stakeholders (§4)

| Who | Ask | Answer in the system | Where |
|---|---|---|---|
| Rohan Bhatt (CEO) | Compliance evidence is "the weakest thing we sell" | Evidence package with hashes per disposition | `application/package.py`, HLD §A4 |
| Dr Anjali Rao | Help with look-ups and arithmetic; no number without an argument | Every finding names its source rows (`source_refs`) and a human action; `reviewer_aid` does arithmetic and is marked "not a recommendation" | assessment JSON, UI result cards |
| Priya Menon | "What did we do last time" | Lane history (same tenant); precedent store DESIGN | LLD §4, `_lane_history` |
| Daniel Okoro (CFO) | $3k/month; shape of the bill on a quiet Sunday | $0 model spend in the kernel; cost table and quiet-Sunday answer | HLD Part B §9 |
| Marieke de Vries (Aurastat) | EU residency; which version produced a recommendation, and notify on change | Regional cells (ADR 0010); manifest per assessment (ADR 0004) | `GET /assessments/{id}` → `manifest` |
| Kavitha Reddy | 72 h / 5 days / next business day; 14 late behind a flat battery | Independent clock, EDF queue, next-business-day not guessed | `domain/obligations.py`, Notification clock tab in the UI |
| Sandeep Iyer | 2,400 rules, 11 forks; "no way of knowing before we shipped it" | Rules as versioned config, hashed; replay diff before shipping | `config/`, ADR 0004 |
| Nikhil Sarin | Meridian Cl.22 | Tenant guard before retrieval; no cross-tenant artefacts | ADR 0006, `tests/test_tenant_isolation.py` |

## 6. Production-grade properties (requested on top of the brief)

| Property | How | Proof |
|---|---|---|
| Lint / format | ruff (E, F, W, I, B, UP, SIM, RUF) | E3a; CI `quality` job |
| Static types | mypy over 42 source files, strict on interfaces, service and ports | E3b |
| Structured logging | JSON lines with `request_id`, route, status, duration (`KCCS_LOG_FORMAT=json`) | `evidence/logs/08_api_server.log` |
| Config via env | `KCCS_*` settings, documented in `.env.example` | `interfaces/api/settings.py` |
| Input validation | pydantic models, path regexes (`^T-[A-Z]{2,20}$`, `^EXC-\d{3,10}$`, `^ASM-[0-9a-f]{24}$`), timezone-aware datetimes | `test_path_and_query_validation`, `test_assess_body_validation`, E30 |
| Consistent errors | RFC 9457 problem+json for every error | `tests/test_api_contract.py`, LLD §12 |
| Health / readiness | `/health/live`, `/health/ready` (workbook loaded, triggers present, assessment hashes intact) | `test_liveness_always_ok_and_readiness_503_before_ingest`, `test_readiness_detects_a_tampered_stored_assessment`, E26, E27 |
| Idempotency | Content-hash assessments (201/200), idempotent ingest, `Idempotency-Key` on transitions | E7, E25, E33; `test_idempotency_key_cannot_be_reused_for_a_different_request` |
| Concurrency safety | `expected_version` → 409 | E43, `test_concurrent_transition_rejected_by_version` |
| Metrics | Prometheus `/metrics` | E44 |
| CI | `.github/workflows/ci.yml`: lint, types, tests on 3.11/3.12/3.13, Docker build + liveness + readiness-503 | workflow file |
| One-command run | `make demo` or `docker compose up --build` | README Quickstart |
