"""Demo orchestration: the end-to-end walk-through used by `kccs-evidence demo` and the e2e script.

Selected cases are chosen by rule from the assessments, never hard-coded outcomes.
The correction is SIMULATED and labelled as such.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from ..domain.records import SourceRecord, SourceSnapshot
from ..domain.temporal import iso
from .access import Principal, TenantAccessDenied
from .assessment import assess_and_store, build_assessment
from .evaluation import evaluate
from .inspection import inspect, write_report
from .package import export_package, verify_package
from .ports import EvidenceStore
from .reporting import write_summary_md

Clock = Callable[[], datetime]
EXTRACT_CUTOFF = "2026-09-14T23:59:00Z"  # latest knowledge the pack can represent


def _dump(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def run_all(store: EvidenceStore, events: list[SourceRecord], cutoff: str, clock: Clock) -> dict[str, dict[str, Any]]:
    tenants = {e.tenant_code for e in events if e.tenant_code}
    p = Principal("batch-evaluator", frozenset(tenants))
    out: dict[str, dict[str, Any]] = {}
    for e in events:
        out[e.record_key], _ = assess_and_store(
            store, p, str(e.tenant_code), e.record_key, knowledge_cutoff=cutoff, clock=clock
        )
    return out


def run_demo(store: EvidenceStore, snap: SourceSnapshot, out: Path, clock: Clock) -> dict[str, Any]:
    """Full walk-through on the workbook: ingest twice, assess all events at two cutoffs, evaluate,
    export packages, a SIMULATED correction, replay and a tenant-isolation probe. Returns the run log."""
    for sub in ("cases", "packages", "evaluation", "data_quality"):
        if (out / sub).is_dir():
            shutil.rmtree(out / sub)
    log: dict[str, Any] = {"ingest": store.ingest_snapshot(snap, f"{snap.extract_date}T00:00:00Z")}
    log["ingest_again_idempotent"] = store.ingest_snapshot(snap, f"{snap.extract_date}T00:00:00Z")
    write_report(inspect(snap), out / "data_quality")
    events = [r for r in snap.records if r.sheet == "01_Excursion_Events"]
    at_alert = run_all(store, events, "alert", clock)
    at_extract = run_all(store, events, EXTRACT_CUTOFF, clock)
    overrides = {r.record_key: r.payload for r in snap.records if r.sheet == "09_Override_Reasons"}
    ev = evaluate(events, at_alert, at_extract, overrides)
    _dump(ev, out / "evaluation" / "summary.json")
    write_summary_md(ev, out / "evaluation" / "summary.md")

    # Selected real cases, chosen by rule from the assessments (not hard-coded outcomes).
    def first(pred):
        return next((e for e in events if pred(at_alert[e.record_key], at_extract[e.record_key])), None)

    picks = {
        "brief_case_EXC-107133": next(e for e in events if e.record_key == "EXC-107133"),
        "sop_overlap": first(lambda a, b: "SOP_REVISION_OVERLAP" in a["blocking_reasons"]),
        "unreferenced_stability_candidate": first(
            lambda a, b: any(f["code"] == "STABILITY_UNREFERENCED_CANDIDATE" for f in a["findings"])
        ),
        "wrong_presentation_referenced": first(
            lambda a, b: any(
                "presentation mismatch" in r
                for r in ((a["evidence"]["stability"]["referenced"] or {}).get("rejection_reasons") or [])
            )
        ),
        "firmware_learned_after_alert": first(
            lambda a, b: (
                "FIRMWARE_BULLETIN_APPLIES" not in {f["code"] for f in a["findings"]}
                and "FIRMWARE_BULLETIN_APPLIES" in {f["code"] for f in b["findings"]}
            )
        ),
        "product_ref_missing": first(lambda a, b: "PRODUCT_REF_MISSING" in a["blocking_reasons"]),
        "product_ambiguous": first(lambda a, b: "PRODUCT_AMBIGUOUS" in a["blocking_reasons"]),
        "next_business_day_policy_incomplete": first(
            lambda a, b: a["notification_track"]["status"] == "POLICY_INCOMPLETE_ESCALATE"
        ),
    }
    cases: dict[str, Any] = {}
    for label, e in picks.items():
        if e is None:
            cases[label] = None
            continue
        a, b = at_alert[e.record_key], at_extract[e.record_key]
        cases[label] = {
            "event_id": e.record_key,
            "tenant": e.tenant_code,
            "at_alert": a["assessment_id"],
            "at_extract": b["assessment_id"],
            "status_at_alert": a["disposition_evidence_status"],
            "blocking_at_alert": a["blocking_reasons"],
            "supersession": b.get("change_from_superseded"),
        }
        _dump(a, out / "cases" / f"{e.record_key}_at_alert.json")
        _dump(b, out / "cases" / f"{e.record_key}_at_extract.json")
        export_package(
            store, Principal("demo-qa", frozenset({e.tenant_code})), a["assessment_id"], out / "packages", iso(clock())
        )
    log["selected_cases"] = cases

    # Correction demo: a SIMULATED source correction (labelled), never presented as real.
    target = picks["brief_case_EXC-107133"]
    orig = store.get_assessment_row(at_alert[target.record_key]["assessment_id"])
    pm_row = next(
        r for r in store.records("02_Product_Master", tenant="T-KAVERI") if r.get("stability_study_ref") == "STB-3584"
    )
    v = store.apply_correction(
        "02_Product_Master",
        pm_row.record_key,
        {"stability_study_ref": "STB-2738"},
        "2026-09-20T10:00:00Z",
        "SIMULATED-QA-DEMO",
        "SIMULATED correction for demonstration: point the pen product at the pen excursion study",
    )
    corrected, _ = assess_and_store(
        store,
        Principal("demo-qa", frozenset({"T-KAVERI"})),
        "T-KAVERI",
        target.record_key,
        knowledge_cutoff="2026-09-21T00:00:00Z",
        clock=clock,
    )
    orig_after = store.get_assessment_row(orig["assessment_id"])
    log["correction_demo"] = {
        "label": "SIMULATED correction (not a real Kestrel change)",
        "record": f"02_Product_Master/{pm_row.record_key}",
        "new_source_version": v,
        "original_assessment": orig["assessment_id"],
        "original_payload_sha256_before": orig["payload_sha256"],
        "original_payload_sha256_after": orig_after["payload_sha256"],
        "original_unchanged": orig["payload_json"] == orig_after["payload_json"],
        "new_assessment": corrected["assessment_id"],
        "supersedes": corrected.get("supersedes"),
        "change": corrected.get("change_from_superseded"),
    }
    _dump(corrected, out / "cases" / f"{target.record_key}_after_simulated_correction.json")
    # Replay of the original assessment after the correction reproduces the same id (knowledge cutoff excludes the correction).
    replay = build_assessment(
        store,
        Principal("demo-qa", frozenset({"T-KAVERI"})),
        "T-KAVERI",
        target.record_key,
        knowledge_cutoff="alert",
        mode="RECONSTRUCTED",
        clock=clock,
    )
    log["correction_demo"]["replay_at_alert_after_correction_same_id"] = (
        replay["assessment_id"] == orig["assessment_id"]
    )
    # Tenant isolation demo
    try:
        build_assessment(
            store,
            Principal("pinnacle-reviewer", frozenset({"T-PINNACLE"})),
            "T-MERIDIAN",
            next(e.record_key for e in events if e.tenant_code == "T-MERIDIAN"),
        )
        log["isolation_demo"] = "FAILED: cross-tenant read allowed"
    except TenantAccessDenied as exc:
        log["isolation_demo"] = f"DENIED as expected: {exc}"
    log["audit_denials"] = len([a for a in store.audit_events() if a["outcome"] == "DENIED"])
    log["packages_verified"] = [verify_package(p) for p in sorted((out / "packages").iterdir())]
    _dump(log, out / "demo_run.json")
    log["assessments_stored"] = store.count_assessments()
    return log
