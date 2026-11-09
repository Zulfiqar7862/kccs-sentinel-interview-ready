"""Markdown rendering of the evaluation summary (reporting only; never an input to an assessment)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def write_summary_md(ev: dict[str, Any], path: Path) -> None:
    L = ["# Assessment summary across the workbook", "", f"> {ev['warning']}", ""]
    for label in ("at_alert_reconstructed", "at_extract_2026-09-14"):
        s = ev[label]
        L += [
            f"## View: {label}",
            "",
            f"- Status: `{s['status']}`",
            f"- Abstaining only on pack-wide gaps (no series, no SOP content): **{s['abstain_only_on_pack_wide_gaps']}** of 420",
            "",
            "| case-specific blocking reason | events |",
            "|---|---|",
        ]
        L += [f"| {k} | {v} |" for k, v in s["case_specific_blockers"].items()]
        L += (
            ["", "| dimension | status counts |", "|---|---|"]
            + [f"| {k} | {v} |" for k, v in s["dimension_status"].items()]
            + [""]
        )
    h = ev["historical_vs_kernel"]
    L += [
        "## Historical engine/assistant output vs kernel (review candidates only)",
        "",
        "| historical rules_engine_recommendation / kernel | n |",
        "|---|---|",
    ]
    L += [f"| {k} | {v} |" for k, v in h["counts"].items()]
    L += [
        "",
        f"Auto-closed by the engine although the kernel finds case-specific evidence gaps: **{h['auto_closed_despite_case_specific_gaps']['n']}**. {h['note']}",
        "",
    ]
    f = ev["firmware_TT-2.14.3"]
    L += [
        "## Firmware TT-2.14.3 (bulletin TT-CB-114)",
        "",
        f"- events {f['events']}, flagged at alert {f['flagged_at_alert']}, flagged at extract {f['flagged_at_extract']}, historically reopened {f['historically_reopened']}",
        f"- {f['note']}",
        "",
    ]
    o = ev["override_reasons"]
    L += [
        "## The 24 written override reasons: would the kernel have surfaced the concern?",
        "",
        f"Summary: `{o['summary']}`",
        "",
        "| event | engine said | reviewer decided | concern | verdict | matching codes | kernel blocking reasons |",
        "|---|---|---|---|---|---|---|",
    ]
    L += [
        f"| {r['event_id']} | {r['engine_said']} | {r['reviewer_decided']} | {r['concern']} | {r['verdict']} | {', '.join(r['kernel_codes_matching'])} | {', '.join(r['kernel_blocking'])} |"
        for r in o["rows"]
    ]
    n = ev["notification_check"]
    L += [
        "",
        "## Notification clock check (rows flagged reportable in the pack)",
        "",
        f"- late in pack: {n['late_in_pack']}; inconsistent with kernel clock: {n['inconsistent_with_kernel_clock']}; not computable (next business day, policy incomplete): {n['not_computable_next_business_day']}",
        "",
        "| event | tenant | window (pack) | kernel due | hours to notify | pack within? | kernel late? | disposition days |",
        "|---|---|---|---|---|---|---|---|",
    ]
    L += [
        f"| {r['event_id']} | {r['tenant']} | {r['window_h_in_pack']} | {r.get('kernel_due_utc')} | {r.get('hours_to_notification', '')} | {r['pack_says_within']} | {r.get('kernel_says_late', 'n/a')} | {r.get('disposition_days', '')} |"
        for r in n["rows"]
    ]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
