# Step-by-step: run and check the submission

This guide takes you from an empty folder to every result, and shows the output to expect at each step. Every command below was run as written on Linux (Python 3.13, 9 Nov 2026) with the supplied workbook. Total time is about 3 minutes.

> **Shortcut:** `make demo` does Steps 3, 5 and 11 in one go, and `make e2e` runs every check in this guide automatically (47 checks, results in `evidence/`).

You need:
- **Python 3.11 or newer** (`python3 --version`);
- **git**;
- the supplied workbook, **`KCCS_Sentinel_Reference_Data_Pack.xlsx`**.

No API keys, accounts or internet access are needed after installation.

---

## Step 1: Get the code

```bash
git clone https://github.com/Zulfiqar7862/kccs-sentinel-interview-ready.git
cd kccs-sentinel-interview-ready
git checkout improve/interview-ready
```

**Expect:** a folder containing `README.md`, `Makefile`, `Dockerfile`, `docs/`, `src/`, `tests/` and `scripts/`.

## Step 2: Add the workbook

The workbook is confidential, so it is not in the repository. Copy it into the `data/` folder:

```bash
mkdir -p data
cp /path/to/KCCS_Sentinel_Reference_Data_Pack.xlsx data/
```

**Expect:** `ls data/` shows `KCCS_Sentinel_Reference_Data_Pack.xlsx`.

## Step 3: Install

```bash
python3 -m venv .venv            # if `python3 --version` is older than 3.11 (common on macOS), use python3.12 or python3.13 here
. .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

**Expect:** the install ends with `Successfully installed … kccs-evidence-kernel-0.2.0 …`. The command `kccs-evidence --help` lists the subcommands `ingest`, `inspect`, `assess`, `export-package`, `verify-package`, `correct`, `demo` and `serve`.

## Step 4: Run the tests

```bash
python -m pytest -v
```

**Expect:** the last line reads **`131 passed`**. If many tests are `skipped`, the workbook is not in `data/` (go back to Step 2).

Optional quality gates (the same as CI): `ruff check src tests`, `ruff format --check src tests` and `mypy`. Each should report no issues.

## Step 5: Run the full demo on the workbook

```bash
kccs-evidence demo --workbook data/KCCS_Sentinel_Reference_Data_Pack.xlsx --out-dir artifacts
```

**Expect** (about 10 seconds), among the printed output:

```
"new_records": 1413                      ← every workbook row loaded once
"unchanged": 1413                        ← loading again adds nothing (safe to repeat)
"isolation_demo": "DENIED as expected: pinnacle-reviewer is not authorised for T-MERIDIAN"
"original_unchanged": true               ← a correction never edits the original assessment
"replay_at_alert_after_correction_same_id": true   ← replaying the past reproduces the same result
assessments stored: 841; outputs in artifacts
```

*Shortcut:* `scripts/run_all.sh` performs Steps 3–5 in one go and saves the test output to `artifacts/test_output.txt`. To run every check in this guide automatically and record the evidence, use `scripts/e2e_check.sh` instead. It writes a pass/fail table and full logs to `evidence/`; the recorded run is in [`evidence/E2E_EVIDENCE.md`](../evidence/E2E_EVIDENCE.md).

## Step 6: Look at the brief's own case (EXC-107133)

Open **`artifacts/cases/EXC-107133_at_alert.json`**. Check these fields:

| Field | What you should see |
|---|---|
| `disposition_evidence_status` | `ABSTAIN_BLOCKING_EVIDENCE_GAPS`: the kernel refuses to conclude, and says why |
| `is_disposition` | `false`: it never makes the product decision |
| `entities.product` | GTIN `08901234500035` resolved within T-KAVERI to `02_Product_Master!R57` |
| `evidence.sop_origin[0]` | `SOP-KAV-9392`, status `CONFLICT_OVERLAPPING_REVISIONS`, in force: `Rev 02`, `Rev 03` |
| `evidence.stability.referenced` | `STB-3584` rejected: wrong presentation (vial, not pen), partially readable, accelerated study |
| `evidence.stability.unreferenced_candidates` | `STB-2738` (pen, "one excursion up to 6 h below 15 °C") admissible but not referenced |
| `notification_track.due_at_utc` | `2026-08-12T06:31:00Z`: counted from the alert (06:31), not the excursion start (06:14) |
| `required_human_actions` | the exact actions a reviewer must take, ending with "Sign or decline the disposition: Site QA" |
| `manifest` | code fingerprint, config hashes and the source versions used, for replay |

## Step 7: Ask the same question "as known then" and "as known later"

```bash
kccs-evidence ingest --workbook data/KCCS_Sentinel_Reference_Data_Pack.xlsx --db artifacts/my.sqlite
kccs-evidence assess --db artifacts/my.sqlite --tenant T-KAVERI --event EXC-107133 \
    --knowledge-cutoff alert --now 2026-11-08T12:00:00Z --out artifacts/then.json
kccs-evidence assess --db artifacts/my.sqlite --tenant T-KAVERI --event EXC-107133 \
    --knowledge-cutoff 2026-09-14T23:59:00Z --now 2026-11-08T12:00:00Z --out artifacts/later.json
```

**Expect:**
```
ASM-ac3e4e7b0db4567a09c245ad status=ABSTAIN_BLOCKING_EVIDENCE_GAPS stored=new
ASM-9be5fe90a6a927d0887e37b5 status=ABSTAIN_BLOCKING_EVIDENCE_GAPS stored=new
```

The first ID is identical on every machine, Python version and run of this commit. The ID is a fingerprint of the evidence, the knowledge cutoff and the exact code and rule versions, so the same inputs always give the same ID. Any change to the code or rules gives a different ID by design.

## Step 8: Check customer separation

```bash
kccs-evidence assess --db artifacts/my.sqlite --tenant T-MERIDIAN --tenant-scope T-PINNACLE --event EXC-110630
echo "exit code: $?"
```

**Expect:** `ACCESS DENIED: cli-reviewer is not authorised for T-MERIDIAN` and `exit code: 3`. A Pinnacle user cannot read Meridian data, and the attempt is recorded in the audit log.

## Step 9: Export an evidence package and prove it cannot be altered

```bash
kccs-evidence export-package --db artifacts/my.sqlite --assessment-id ASM-ac3e4e7b0db4567a09c245ad \
    --tenant-scope T-KAVERI --out-dir artifacts/my_packages
kccs-evidence verify-package artifacts/my_packages/ASM-ac3e4e7b0db4567a09c245ad
```

**Expect:** `"ok": true`. Now change the package and verify again:

```bash
sed -i 's/ABSTAIN_BLOCKING_EVIDENCE_GAPS/READY_FOR_QA_REVIEW/' artifacts/my_packages/ASM-ac3e4e7b0db4567a09c245ad/assessment.json
kccs-evidence verify-package artifacts/my_packages/ASM-ac3e4e7b0db4567a09c245ad
```

**Expect:** `"ok": false` and `"problems": ["hash mismatch assessment.json"]`, with exit code 2. (On macOS, use `sed -i ''`.)

## Step 10: Read the results across all 420 alerts

| File | What it shows |
|---|---|
| `artifacts/evaluation/summary.md` | Abstentions and blocking reasons per alert, the firmware-bulletin replay, whether the 24 written reviewer overrides would have been surfaced (including the misses), and the notification-deadline check |
| `artifacts/data_quality/report.md` | Workbook inspection: sheets, missing values, join problems, the 27 overlapping SOP revision pairs, stability-index issues |
| `artifacts/demo_run.json` | Machine-readable proof of each demo claim from Step 5 |

These figures come from a stratified evidence pack, not a random sample. They are **not** accuracy or automation-rate estimates.

## Step 11: Run the REST API and web UI

```bash
KCCS_FIXED_NOW=2026-11-08T12:00:00Z KCCS_DB_PATH=artifacts/api/kernel.sqlite KCCS_ARTIFACTS_DIR=artifacts/api \
  kccs-evidence serve --port 8000
```

**Expect:** the log line `workbook autoloaded`, then `Uvicorn running on http://127.0.0.1:8000`. In a second terminal:

```bash
curl -s http://127.0.0.1:8000/health/ready
# {"ready":true,"workbook_loaded":true,"append_only_triggers":true,...}
curl -s -H "X-Actor: demo-qa" -H "X-Tenant-Scope: T-KAVERI" -H "Content-Type: application/json" \
     -d '{"knowledge_cutoff":"alert"}' http://127.0.0.1:8000/api/v1/tenants/T-KAVERI/events/EXC-107133/assessments | head -c 160
# {"stored":"new","assessment_id":"ASM-ac3e4e7b0db4567a09c245ad","status":"ABSTAIN_BLOCKING_EVIDENCE_GAPS",...
curl -s -o /dev/null -w '%{http_code}\n' -H "X-Actor: demo-qa" -H "X-Tenant-Scope: T-KAVERI" \
     http://127.0.0.1:8000/api/v1/tenants/T-AURA/events
# 403
```

Open **http://127.0.0.1:8000/ui/** (web UI) and **http://127.0.0.1:8000/docs** (OpenAPI). The UI click path is in [`INTERVIEW_GUIDE.md`](INTERVIEW_GUIDE.md) §3.3.

## Step 12: Docker (optional)

```bash
docker compose up --build
curl -s http://localhost:8000/health/ready
```

**Expect:** `"ready":true` once the container is healthy. Without the workbook in `data/`, readiness is 503, which is the intended behaviour.

## Step 13: Read the written deliverables

| Order | File | Deliverable |
|---|---|---|
| 1 | `FINAL_REPORT.md` | Overview |
| 2 | `docs/01_where_we_land.md` | Where I land: requirements, non-goals, rollout, contradictions, board targets |
| 3 | `docs/02_architecture_hld.md`, `docs/03_detailed_design_lld.md` | The design |
| 4 | `docs/04_data_findings_and_assumptions.md` | Data findings |
| 5 | `docs/05_validation_and_operations.md` | How correctness is checked today and monitored later |
| 6 | `docs/06_working_log.md` | Working log |
| 7 | `docs/07_review_walkthrough.md` | 20-minute walkthrough and hard questions |
| 8 | `docs/INTERVIEW_GUIDE.md` | Pitch, demo script, Q&A, code tour |
| 9 | `docs/USE_CASE_COVERAGE.md`, `docs/adr/` | Requirement → code → endpoint → test; decisions |

---

## If something goes wrong

| Symptom | Fix |
|---|---|
| `Workbook not found at data/…` | Put the file in `data/` with exactly this name: `KCCS_Sentinel_Reference_Data_Pack.xlsx` |
| Many `skipped` in Step 4 | Same cause: the workbook is missing from `data/` |
| `error: externally-managed-environment` | Activate the virtual environment first (Step 3) |
| `requires a different Python` or `Python 3.11 or newer is required` | Your `python3` is too old. Install 3.11+ (macOS: `brew install python@3.12`) and recreate the environment with it (`rm -rf .venv && python3.12 -m venv .venv`) |
| `NOT FOUND: … not found for tenant …` | The database has not been loaded yet (run `kccs-evidence ingest` first), or the event belongs to another customer |
| `kccs-evidence: command not found` | Activate the virtual environment, or use `python -m kccs_evidence …` instead |
| `ZoneInfoNotFoundError` | Re-run `pip install -e ".[dev]"`, which installs `tzdata` |
| Step 7 prints a different ID | Check that the workbook is the unmodified original (its SHA-256 starts with `9fe3fad7d0f77a5f`) and that the code is the commit recorded in `evidence/environment.txt`. Any change under `domain/`, `application/`, `infrastructure/` or `config/` changes the ID by design |
