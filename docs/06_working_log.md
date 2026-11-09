# 06 — Working log (this session)

**Honesty statement.** This repository was produced in **AI-assisted sessions on 8–9 November 2026** using an AI coding agent (Hoplite, model `claude-opus-5-5`) on Zulfiqar's instruction. The agent wrote the code, tests and documents. The entries below record what was actually done and observed in that session, from the tool outputs. They are not reconstructed from memory, and nothing is invented about earlier sessions. **Zulfiqar's own review, disagreements and time spent are not yet recorded.** Section 3 is for that, and it should be completed before submission. Chain-of-thought is not reproduced; only decisions and the evidence for them.

## 1. Session steps

| # | Question / hypothesis | Evidence examined | Considered | Kept / rejected and why | Mistake or uncertainty → how detected | Files / decisions |
|---|---|---|---|---|---|---|
| 1 | What is in the workspace? | repo listing, `git log` | Build on the existing scaffold vs replace it | **Replaced.** The scaffold (~1,300 lines) had a rules function that read `triage_outcome` as an input (outcome leakage) and invented confidence numbers | Found by reading `prototype/src/adjudication/rules/engine.py`; old code kept in git history (`9f98e8e`) | whole repo |
| 2 | What does the brief actually ask? | full PDF (8 pages) via `pdftotext` | — | Noted: deliverables A–D; the brief's contact is **sudhanshu@fourkites.com**. I first wrongly concluded "Sangeeta" was not involved; the candidate then shared her 4 Nov instructions email, so the cover note now replies to her and copies Sudhanshu | Tool condenser summarised long outputs; switched to small slices so the raw text was read | email draft |
| 3 | Is the core problem evidence, not prediction? | `09` (24 reasons), `14` (6 incidents), `10` (12 questions) | Prompt/model improvement vs evidence kernel | Hypothesis **kept with refinement**: evidence must be temporally qualified (AUD-2603 vs INC-2506) | ~20/24 is my reading of the reasons, not a computed figure; stated as such | `01` §1 |
| 4 | Profile all 15 tabs | per-sheet scripts in `scratch/` (inline heredocs were blocked by the sandbox) | pandas vs openpyxl | **openpyxl only**: keeps raw types and GTIN strings; fewer dependencies | — | `sources.py` |
| 5 | Interval convention for SOPs | `05` windows | closed vs half-open | **Half-open**: 115 hand-overs have `to == next from` | — | `temporal.py` |
| 6 | Can `07` aliases resolve products? | `07` has no tenant column; `12!R6` Cl.22 | use as lookup / use as hint / quarantine | **Quarantine product aliases**; facility/carrier aliases allowed as provisional hints | Trade-off: 81 product refs stay unresolved. Accepted and shown in the summary | `access.py`, config |
| 7 | EXC-107133 evidence chain | `02!R57`, `06!R105–108`, `05!R202–204`, `08` QL-02111 | — | Found: master references a vial accelerated study (STB-3584); pen study STB-2738 unreferenced; Rev 02/03 overlap; brief 09:30 UTC vs log 06:54 UTC | — | `04` |
| 8 | First full run over 420 events | smoke run | — | — | **Wrong assumption:** only "Temperature Excursion Management" governs excursions. 164 `NO_SOP_INDEXED` = all of T-VIRENT. Kept as a real finding; the message now lists the tenant's other titles without assuming them | `policy_sop.py` |
| 9 | Presentation check | EXC-107133 output | token set over the whole study text | — | **Bug:** brand token "SoloJet" made "Glucodyne SoloJet — vial" look like a pen. Detected because the expected mismatch was missing from STB-3584's rejection reasons. Fixed: explicit presentation words beat brand-derived tokens | `stability.py`, lexicon |
| 10 | Evaluate against override reasons | evaluation table | — | — | **Bug:** EXC-110497 NOT_SURFACED. "Rinvatec PFS 40 — vial" contains "PFS" in the product name. Fixed: a study's presentation comes from its suffix after "—" or the trailing parenthesis | `study_presentations()` |
| 11 | Same | evaluation table | — | — | **Self-serving check caught:** the EXC-110581 expectation accepted any `CARRIER_RESOLVED`, so it would "pass" whatever contract was picked. Changed to require CNT-2023-0441 (the GmbH) | `evaluation.py` |
| 12 | Conflict spike | case-specific blockers jumped to 150 after fix 10 | — | — | Product-master "Refer QA" was being compared as a competing limit. It is a deferral, already flagged separately; excluded from the conflict check (116 after the fix) | `stability.py` |
| 13 | Correction demo | `demo_run.json`: `replay_at_alert_after_correction_same_id: false` | — | — | **Temporal leak bug:** reconstructed replay read the store "as now", so a correction recorded on 2026-09-20 leaked into the at-alert replay. Fixed with a store cutoff of max(cutoff, baseline snapshot). Regression test added | `assessment.py`, `test_correction_produces_new_assessment…` |
| 14 | Test failures | pytest output | — | — | (a) Append-only trigger test passed vacuously on empty tables: insert rows first. (b) Strict mode could not see the alert itself: subject alert taken from the access-checked view. (c) "recommend" check matched the phrase "Not a recommendation": tightened to disposition values. (d) `"notes"` is a generic key: excluded from the static outcome-field scan | tests |
| 15 | Demo hygiene | `artifacts/packages` held 32 directories | — | — | Stale outputs from earlier runs: demo now clears its own subdirectories | `cli.py` |
| 16 | Remaining honest gaps | evaluation | retrofit expectations to pass | **Rejected retrofitting.** EXC-110476 stays NOT_SURFACED; EXC-110602 SURFACED_ONLY_GENERICALLY | — | `05` |
| 17 | Docs consistency | own numbers | — | — | Wrote "57 annexure revisions" in `04`; recount from the profile gave 102 (40+33+29). Corrected | `04` |
| 18 | Final check against a fresh clone | clean-clone `run_all.sh` artifacts | — | — | **Stale claims:** the docs said "every event has a case-specific blocker" (true before fix 12) and "42 packages". The clean run shows 8 events with only pack-wide gaps (4 T-CAMPOS, 4 T-PINNACLE) and 6 packages. Docs corrected from the clean-run output | `05`, `07`, `FINAL_REPORT.md` |

Discarded approaches, with reasons:
- **Ranking ambiguous candidates:** it hides conflicts the reviewer must see.
- **Fuzzy product matching:** this is exactly how the wrong presentation gets picked.
- **Treating 1.8 °C as a fixed correction:** the bulletin says "up to".
- **Using `reg_window_hours=24` as "next business day":** it is not equivalent.
- **Shipping a dashboard:** the brief asks for the hardest part, not the most demonstrable.
- **Self-hosted model for prohibited tenants:** one instance is $4,139/month, above the budget.

## 2. Where the AI was confidently wrong (and how it was caught)

1. Assumed a single SOP title governs excursions for all tenants. Caught by the 164-count spike on T-VIRENT (step 8).
2. Presentation logic was wrong twice, in two different ways (steps 9 and 10). Caught by reading a real case output and by the override evaluation.
3. Believed reconstructed replay was leak-free. Caught by the correction demo's own reproducibility check (step 13).
4. Wrote evaluation expectations that could not fail (step 11), and a test that passed vacuously (step 14a).
5. Stated a wrong count in a document (step 17).

Pattern: every error was caught by a check that compared the output against **a specific real record** or **a reproducibility invariant**, not by re-reading code.

## 3. Review after the first build (8–9 November)

After the first version was complete, Zulfiqar reviewed it, had it reviewed independently by a second AI tool (Perplexity), and checked it against the recruiter's instruction email. What came out of that review:

| Input | What it said | Kept, changed or rejected | Why |
|---|---|---|---|
| Instruction email (4 Nov) | The submission goes to the recruiter, not only to the brief's contact | **Changed:** the cover note now goes to the recruiter. The AI had wrongly concluded she was not involved, because she is not named in the brief (step 2) | The email outranks an inference from the brief |
| External review | Make the 76 tests visible as claims, not a count | **Kept:** README "What the tests prove" table, mapping each claim to a test file | A reviewer should be able to check a claim without reading every test |
| External review | Explain early why every alert abstains | **Kept:** moved to the top of the README and FINAL_REPORT §2 | Otherwise "everything abstains" reads as "does nothing" |
| External review | Separate observed facts from the system's interpretations | **Kept:** fact vs interpretation table in FINAL_REPORT §3, each with the approver it needs | The interpretations are policy choices, not data |
| External review | List the 8 alerts that are blocked only by pack-wide gaps | **Kept:** table in FINAL_REPORT §2. Two of them *exceed* the study's limit, which shows that "unblocked" does not mean "safe" | The claim needed to be checkable |
| External review | Split `assessment.py`; add manifest-stability tests; add drift checks | **Rejected for now:** idempotency, actor-independence and outcome-field independence tests already existed. Refactoring after submission was not worth the risk | Recorded as a production follow-up |
| Request for runnable proof | Record an end-to-end run, not just claim one | **Added:** `scripts/e2e_check.sh` and `evidence/` (25 checks with logs) | The reviewer can see the results without running anything |

Defects found during this review and fixed (9 November):

| # | Defect | How it was found | Fix |
|---|---|---|---|
| 19 | The evidence-assessment sequence diagram in `docs/02` **did not render on GitHub**: semicolons inside a message are statement separators in Mermaid | Every diagram was rendered with the official Mermaid CLI. One failed with a parse error at line 10 | Removed the semicolons. All 5 diagrams now render. The architecture diagram was also switched to top-to-bottom for readability |
| 20 | On macOS the scripts would pick Apple's bundled `python3` (often 3.9), and the install would fail with an unclear pip error | Reviewing the scripts for machines other than the build sandbox | `scripts/_python.sh` picks Python 3.11 or newer, or stops with a clear message. The scripts no longer use the Linux-only `sha256sum` |
| 21 | Asking the CLI for an unknown event, or querying an empty database, printed a Python traceback | Running the README commands with wrong inputs | Clear one-line `NOT FOUND` / `ERROR` messages with non-zero exit codes, plus a hint to run `ingest` |
| 22 | Notes meant only for the candidate (an unchecked to-do list, blank fields, a draft email, a checklist) were visible to reviewers | Reading the repository as a reviewer would | Removed or replaced with factual content |

Time spent is stated in the covering note. The full chat transcript of the AI-assisted sessions is available on request.

## 4. Second session: interview-ready restructure (9 November, branch `improve/interview-ready`)

**What it was for.** Zulfiqar asked for the repo to be made interview-ready:
- a clear structure;
- HLD and LLD good enough for an engineering panel;
- a working system that can be demonstrated (API + UI);
- production basics: lint, types, logging, config, validation, errors, health, idempotency, CI, Docker;
- a coverage matrix from the brief to the code.

The work was done by an AI agent (Grok Bot) on his instruction. Decisions and observed results are below. Every number comes from a run.

**Skills consulted (public agent-skill files, read before starting):**
- the FastAPI project's own agent skill (`fastapi/.agents/skills/fastapi/SKILL.md`), for `Annotated` dependencies, routers, sync handlers for CPU-bound work, and lifespan;
- C4/arc42/ADR documentation skills: gauravs19/enterprise-architecture-skill, alicommit-malp/generating-arc42, clenci/arch-advisor;
- Mermaid diagram skills: M2LabOrg/agent-skills, ccheney/robust-skills;
- wshobson fastapi-templates.

| # | Question / hypothesis | Evidence examined | Kept / rejected and why | Mistake or uncertainty → how detected | Files |
|---|---|---|---|---|---|
| 23 | Baseline before touching anything | `scripts/e2e_check.sh` on `main` | Baseline 25/25 checks, 76 tests; outputs saved to compare later | **Script bug:** the EXC-107133 excerpt step ran *after* `deactivate`, so `python` was not found and the excerpt file was deleted. Fixed by moving the step before `deactivate` | `scripts/e2e_check.sh` |
| 24 | Restructure into layers without changing behaviour | Baseline evaluation summary, data-quality report and case JSONs | **Kept:** hexagonal layers `domain` / `application` / `infrastructure` / `interfaces`, with an AST test enforcing inward-only imports. After the move, the evaluation summary and data-quality report were **identical** to the baseline; case JSONs differed only in manifest, IDs and versions | — | `src/kccs_evidence/*`, `tests/test_architecture.py` |
| 25 | Should the UI/API change assessment IDs? | Fingerprint covered every `.py` file | **Changed:** the fingerprint now covers `domain`, `application`, `infrastructure` and `config` only. A UI fix must not change the evidence ID; a rule change must | — | `application/assessment.py`, ADR 0004 |
| 26 | Supersession under a fixed clock | Comparing case JSONs with the baseline | — | **Real bug:** with a fixed demo clock, every assessment got the same `first_stored_at`, so "the previous assessment" was picked by hash order (`ORDER BY assessment_id`). Fixed to `ORDER BY first_stored_at, rowid`, with a regression test | `infrastructure/sqlite_store.py`, `tests/test_service.py` |
| 27 | Where does obligation state live across restarts? | The ledger was in memory only | **Kept the pure ledger** and added an append-only `obligation_transition` log (event sourcing). It is rebuilt at start-up and after ingest. Optimistic `expected_version` and `Idempotency-Key` | Considered a mutable `obligation` table; rejected because it would be the only mutable table | `application/service.py`, ADR 0005 |
| 28 | Type checking | mypy on the whole package | **Kept strict** on interfaces, service and ports | 42 errors on first run, mostly missing `None` guards (e.g. a SOP row without `effective_from`). Fixed; such a row is now explicitly **not in force** (fail closed) | `domain/policy_sop.py`, `application/assessment.py` |
| 29 | Pydantic validator for aware datetimes | API tests | Replaced the custom validator with `AwareDatetime` | `NameError` in a custom validator, found by the first API test run | `interfaces/api/schemas.py` |
| 30 | Obligation queue "as of" a past time | UI walk-through (37 rows at 2026-07-29, mostly long-breached) and then the queue code | — | **Future leakage in the queue:** the queue did not filter by `clock_start`, so alerts received *after* `as_of` could be listed. Found by reading the code after the UI queue looked wrong. Fixed: only obligations with `clock_start <= as_of`; added `received_within_hours` and a test | `application/service.py`, `test_obligation_queue_never_shows_alerts_received_after_as_of` |
| 31 | Do the old helper scripts still work after the move? | Running `scripts/run_all.sh` and `scripts/inspect_workbook.py` | — | **Both broken:** they imported the old module paths (`kccs_evidence.cli`, `kccs_evidence.inspection`). Found only by running them. Fixed and re-run (131 passed, 841 assessments) | `scripts/` |
| 32 | Version numbers | `pyproject.toml` vs `__init__.py` | — | `pyproject` said 0.1.0 while the code said 0.2.0. Aligned to 0.2.0 | `pyproject.toml` |
| 33 | Reviewer questions coverage | Coverage matrix draft | **Added** one test per tab-10 question that the pack can answer, and a test that Q6 (duplicates) is *not* claimed | Writing the matrix showed several questions were covered only by the replay evaluation, with no unit test | `tests/test_reviewer_questions.py` |
| 34 | Docker in the build sandbox | `docker compose up` | The image builds and the container becomes healthy and ready | The sandbox had no bridge networking; the build used `--network host`, and compose needed a local override file. **Not** a repo change; stated as a limitation | — |

**What was deliberately not done in this session:**
- case workflow;
- OIDC;
- Postgres adapter;
- connectors.

They stay [DESIGN]. Adding them would have produced more code to defend and less judgement, which the brief warns against (§10).
