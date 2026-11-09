# End-to-end test evidence

**Result: 47 of 47 checks passed** on 9 November 2026 (13:56 UTC, 14:56 Europe/Berlin). The run used the supplied workbook, a fresh Python environment, and a live API server.

The run was produced by `scripts/e2e_check.sh` (also `make e2e`). To repeat it yourself:

```bash
mkdir -p data && cp /path/to/KCCS_Sentinel_Reference_Data_Pack.xlsx data/
scripts/e2e_check.sh          # last line: checks: 47, failed: 0
```

The script rebuilds this whole `evidence/` folder, apart from this page, and exits 0 only if every check passes.

## What was tested

| Item | Value |
|---|---|
| Code tested | commit `5c98a9e3d40030246a478504745de1fde194cfd4` (branch `improve/interview-ready`) |
| Workbook | `KCCS_Sentinel_Reference_Data_Pack.xlsx`, 221,860 bytes, SHA-256 `9fe3fad7d0f77a5fbdaa0f8ce70336a911a8725d38d057b9d9d777c06ea57db3` |
| Environment | Python 3.13.5 on Linux; dependency versions in `pip_freeze.txt` |
| Duration | about 30 seconds, including the fresh install |

The workbook is **not** in this folder or in the repository, because it is confidential. Only derived results are kept here.

## Stages

1. **Install:** a fresh venv runs `pip install -e .[dev]`.
2. **Quality gates:** ruff (lint + format check) and mypy.
3. **Tests:** the full pytest suite. It must report 131 passed, with nothing skipped or failed.
4. **CLI:** workbook inspection, then the full demo (ingest, re-ingest, isolation, correction, replay, packages), then individual CLI commands.
5. **API:** `kccs-evidence serve` is started with a fixed clock. Every endpoint is then called with curl: health, readiness, events, assess, history, packages, tamper demo, obligations, transitions, metrics, the UI and the OpenAPI docs. Logs are in `logs/08_api_server.log` and `logs/09_api_calls.log`.

## Same result on every supported Python version

The same commit and workbook were tested in a fresh clone (`git clone -b improve/interview-ready`) with a separate environment for each version:

| Python | How | Tests | mypy | EXC-107133 at alert |
|---|---|---|---|---|
| 3.13.5 | `scripts/e2e_check.sh` (this folder) | 131 passed | clean | `ASM-ac3e4e7b0db4567a09c245ad` |
| 3.12.16 | `uv venv -p 3.12`, then pytest and the CLI | 131 passed | clean | `ASM-ac3e4e7b0db4567a09c245ad` |
| 3.11.13 | `uv venv -p 3.11`, then pytest and the CLI | 131 passed | clean | `ASM-ac3e4e7b0db4567a09c245ad` |

Without the workbook, 54 tests pass and 77 skip. These are the API contract, architecture and synthetic-fixture tests.

**Docker** (same fresh clone):
- The image `kccs-evidence-kernel:local` builds and runs as the non-root user `kccs`.
- With `./data` mounted, readiness is 200 and the EXC-107133 ID is the same as above.
- Without the workbook, liveness is 200 and readiness is 503.
- `docker compose up` reached `healthy` and served `/ui/`. The build sandbox has no bridge networking, so it was run with a local host-network override.

All runs were on Linux; macOS and Windows were not tested.

## Results

| ID | Check | Expected | Observed | Result |
|---|---|---|---|---|
| E1 | Fresh install (pip install -e .[dev]) | 0 | 0 | PASS |
| E2 | Test suite exit code | 0 | 0 | PASS |
| E3 | Tests passed (none failed or skipped) | 131 passed | 131 passed | PASS |
| E3a | Lint and format (ruff) | 0 | 0 | PASS |
| E3b | Static types (mypy) | 0 | 0 | PASS |
| E4 | Workbook inspection report written | 0 | 0 | PASS |
| E5 | Full demo exit code | 0 | 0 | PASS |
| E6 | Workbook rows ingested | 1413 | 1413 | PASS |
| E7 | Re-ingest is idempotent (new records) | 0 | 0 | PASS |
| E8 | Cross-tenant read denied in demo | True | True | PASS |
| E9 | Correction leaves original assessment byte-identical | True | True | PASS |
| E10 | At-alert replay after correction reproduces original ID | True | True | PASS |
| E11 | Assessments stored | 841 | 841 | PASS |
| E12 | All demo evidence packages verify | True | True | PASS |
| E13 | EXC-107133 abstains (no disposition) | ABSTAIN_BLOCKING_EVIDENCE_GAPS False | ABSTAIN_BLOCKING_EVIDENCE_GAPS False | PASS |
| E14 | EXC-107133 product resolved within T-KAVERI | 02_Product_Master!R57 | 02_Product_Master!R57 | PASS |
| E15 | EXC-107133 SOP overlap detected | SOP-KAV-9392 CONFLICT_OVERLAPPING_REVISIONS ['Rev 02', 'Rev 03'] | SOP-KAV-9392 CONFLICT_OVERLAPPING_REVISIONS ['Rev 02', 'Rev 03'] | PASS |
| E16 | EXC-107133 wrong-presentation study rejected | STB-3584 False | STB-3584 False | PASS |
| E17 | EXC-107133 pen study offered as candidate | True | True | PASS |
| E18 | EXC-107133 notification deadline from alert receipt | 2026-08-12T06:31:00Z | 2026-08-12T06:31:00Z | PASS |
| E19 | Assessment ID reproducible across runs | ASM-ac3e4e7b0db4567a09c245ad | ASM-ac3e4e7b0db4567a09c245ad | PASS |
| E20 | Later knowledge cutoff gives a different assessment | True | True | PASS |
| E21 | CLI cross-tenant read refused (exit code) | 3 | 3 | PASS |
| E22 | Exported package verifies | 0 | 0 | PASS |
| E23 | Other tenant cannot export the package (exit code) | 3 | 3 | PASS |
| E24 | Tampered package rejected (exit code) | 2 | 2 | PASS |
| E25 | CLI re-ingest adds nothing | new_records: 0 | new_records: 0 | PASS |
| E26 | API liveness | 200 | 200 | PASS |
| E27 | API readiness (workbook autoloaded, integrity self-check) | True | True | PASS |
| E28 | API lists T-KAVERI events without outcome fields | True | True | PASS |
| E29 | API missing identity headers | 401 | 401 | PASS |
| E30 | API invalid event id | 422 | 422 | PASS |
| E31 | API assess EXC-107133 abstains | ABSTAIN_BLOCKING_EVIDENCE_GAPS False | ABSTAIN_BLOCKING_EVIDENCE_GAPS False | PASS |
| E32 | API assessment ID equals CLI assessment ID | ASM-ac3e4e7b0db4567a09c245ad | ASM-ac3e4e7b0db4567a09c245ad | PASS |
| E33 | API re-assess is idempotent | 200 | 200 | PASS |
| E34 | API later cutoff supersedes the first | ASM-ac3e4e7b0db4567a09c245ad | ASM-ac3e4e7b0db4567a09c245ad | PASS |
| E35 | API cross-tenant event read | 403 | 403 | PASS |
| E36 | API cross-tenant assessment read | 403 | 403 | PASS |
| E37 | API package export verifies | True | True | PASS |
| E38 | API package zip download | 200 | 200 | PASS |
| E39 | API tampered package copy fails verification | True False | True False | PASS |
| E40 | API obligation for EXC-107133 due from alert receipt | 2026-08-12T06:31:00Z | 2026-08-12T06:31:00Z | PASS |
| E41 | API obligation transition needs REGULATORY_AFFAIRS | 403 | 403 | PASS |
| E42 | API obligation transition applied | NOTIFIABLE_CONFIRMED 2 | NOTIFIABLE_CONFIRMED 2 | PASS |
| E43 | API stale expected_version rejected | 409 | 409 | PASS |
| E44 | API metrics report ready and no hash failures | True | True | PASS |
| E45 | Web UI and OpenAPI docs served | 200 200 200 | 200 200 200 | PASS |

The same table, in machine-readable form, is in `results/checks.tsv`.

## Files in this folder

| File | What it is |
|---|---|
| `RESULT.txt` | One-line outcome: `checks: 47, failed: 0` |
| `environment.txt` | Date, commit, Python version, OS, workbook hash |
| `pip_freeze.txt` | Exact dependency versions installed |
| `logs/01_install.log` | Full install output |
| `logs/02_pytest.log` | Full test output, with each of the 131 tests listed by name |
| `logs/03_inspect.log` | Workbook inspection run |
| `logs/04_demo.log` | Full demo console output |
| `logs/05_cli.log` | Output of each command-line check |
| `logs/06_lint.log`, `logs/07_mypy.log` | ruff and mypy output |
| `logs/08_api_server.log` | JSON structured server log (one line per request, with `request_id`) |
| `logs/09_api_calls.log` | Every curl call, with small responses verbatim and only a size and key summary of large ones (no raw workbook rows) |
| `results/EXC-107133_assessment_excerpt.json` | The brief's case, key fields |
| `results/evaluation_summary.md` | Replay over all 420 events vs historical outcomes and the 24 override reasons |
| `results/data_quality_report.md` | Workbook inspection report |
| `results/demo_run.json` | Machine-readable proof of each demo claim |
