"""Command-line interface: thin adapter that wires infrastructure to application use cases.

Exit codes: 0 ok · 2 invalid input / verification failed · 3 access denied · 4 not found.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from ..application.access import Principal, TenantAccessDenied
from ..application.assessment import assess_and_store
from ..application.demo import run_demo
from ..application.inspection import inspect, write_report
from ..application.package import export_package, verify_package
from ..domain.temporal import UTC, iso, parse_iso_utc
from ..infrastructure.sqlite_store import Store
from ..infrastructure.workbook import load_workbook_snapshot

DEFAULT_DB = "artifacts/kernel.sqlite"
EXIT_INVALID, EXIT_DENIED, EXIT_NOT_FOUND = 2, 3, 4


def fixed_clock(ts: str | None) -> Callable[[], datetime]:
    if ts:
        t = parse_iso_utc(ts)
        return lambda: t
    return lambda: datetime.now(UTC)


def _principal(args: argparse.Namespace) -> Principal:
    tenants = frozenset(t.strip() for t in (args.tenant_scope or args.tenant or "").split(",") if t.strip())
    return Principal(args.actor, tenants)


def _dump(obj: Any, path: Path | None) -> None:
    text = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def cmd_ingest(args: argparse.Namespace) -> None:
    snap = load_workbook_snapshot(args.workbook)
    recorded = args.recorded_at or f"{snap.extract_date}T00:00:00Z"
    stats = Store(args.db).ingest_snapshot(snap, recorded)
    print(
        json.dumps({"snapshot_id": snap.snapshot_id, "file_sha256": snap.file_sha256, "recorded_at": recorded, **stats})
    )


def cmd_inspect(args: argparse.Namespace) -> None:
    path = write_report(inspect(load_workbook_snapshot(args.workbook)), args.out_dir)
    print(f"wrote {path} and {Path(args.out_dir) / 'report.json'}")


def cmd_assess(args: argparse.Namespace) -> None:
    payload, inserted = assess_and_store(
        Store(args.db),
        _principal(args),
        args.tenant,
        args.event,
        knowledge_cutoff=args.knowledge_cutoff,
        mode=args.mode,
        clock=fixed_clock(args.now),
    )
    _dump(payload, Path(args.out) if args.out else None)
    print(
        f"{payload['assessment_id']} status={payload['disposition_evidence_status']} "
        f"stored={'new' if inserted else 'existing'}",
        file=sys.stderr,
    )


def cmd_export(args: argparse.Namespace) -> None:
    out = export_package(
        Store(args.db), _principal(args), args.assessment_id, args.out_dir, iso(fixed_clock(args.now)())
    )
    print(json.dumps(verify_package(out)))


def cmd_verify(args: argparse.Namespace) -> None:
    res = verify_package(args.package)
    print(json.dumps(res))
    sys.exit(0 if res["ok"] else EXIT_INVALID)


def cmd_correct(args: argparse.Namespace) -> None:
    changes = dict(kv.split("=", 1) for kv in args.set)
    v = Store(args.db).apply_correction(args.sheet, args.key, changes, args.recorded_at, args.actor, args.reason)
    print(json.dumps({"sheet": args.sheet, "record_key": args.key, "new_version": v}))


def cmd_demo(args: argparse.Namespace) -> None:
    out = Path(args.out_dir)
    db = out / "kernel.sqlite"
    if db.exists():
        db.unlink()
    store = Store(db)
    log = run_demo(store, load_workbook_snapshot(args.workbook), out, fixed_clock(args.now))
    print(
        json.dumps(
            {k: log[k] for k in ("ingest", "ingest_again_idempotent", "isolation_demo", "audit_denials")}, indent=1
        )
    )
    print(json.dumps(log["correction_demo"], indent=1, default=str))
    print(f"assessments stored: {log['assessments_stored']}; outputs in {out}")


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    from .api.settings import Settings

    settings = Settings.from_env()
    uvicorn.run(
        "kccs_evidence.interfaces.api.app:create_app",
        factory=True,
        host=args.host or settings.host,
        port=args.port or settings.port,
        log_config=None,
    )


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="kccs-evidence", description="KCCS Sentinel evidence kernel")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest", help="load the workbook into the append-only store (idempotent)")
    s.add_argument("--workbook", required=True)
    s.add_argument("--db", default=DEFAULT_DB)
    s.add_argument("--recorded-at")
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("inspect", help="write a data-quality report for the workbook")
    s.add_argument("--workbook", required=True)
    s.add_argument("--out-dir", default="artifacts/data_quality")
    s.set_defaults(fn=cmd_inspect)

    s = sub.add_parser("assess", help="build and store one assessment")
    s.add_argument("--db", default=DEFAULT_DB)
    s.add_argument("--tenant", required=True)
    s.add_argument("--event", required=True)
    s.add_argument("--actor", default="cli-reviewer")
    s.add_argument("--tenant-scope", help="comma list of tenants the actor may access (default: --tenant)")
    s.add_argument("--knowledge-cutoff", default="alert", help="alert | now | ISO-8601 UTC")
    s.add_argument("--mode", default="RECONSTRUCTED", choices=["RECONSTRUCTED", "STRICT"])
    s.add_argument("--now")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_assess)

    s = sub.add_parser("export-package", help="export a hashed evidence package")
    s.add_argument("--db", default=DEFAULT_DB)
    s.add_argument("--assessment-id", required=True)
    s.add_argument("--out-dir", default="artifacts/packages")
    s.add_argument("--actor", default="cli-reviewer")
    s.add_argument("--tenant-scope", required=True)
    s.add_argument("--tenant")
    s.add_argument("--now")
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("verify-package", help="recompute every hash in a package")
    s.add_argument("package")
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("correct", help="append a corrected version of a source record")
    s.add_argument("--db", default=DEFAULT_DB)
    s.add_argument("--sheet", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--set", nargs="+", required=True, metavar="COL=VALUE")
    s.add_argument("--reason", required=True)
    s.add_argument("--actor", required=True)
    s.add_argument("--recorded-at", required=True)
    s.set_defaults(fn=cmd_correct)

    s = sub.add_parser("demo", help="full end-to-end walk-through on the workbook")
    s.add_argument("--workbook", required=True)
    s.add_argument("--out-dir", default="artifacts")
    s.add_argument("--now", default="2026-11-08T12:00:00Z")
    s.set_defaults(fn=cmd_demo)

    s = sub.add_parser("serve", help="run the REST API and web UI (settings from KCCS_* env vars)")
    s.add_argument("--host")
    s.add_argument("--port", type=int)
    s.set_defaults(fn=cmd_serve)
    return ap


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.fn(args)
    except TenantAccessDenied as exc:
        print(f"ACCESS DENIED: {exc}", file=sys.stderr)
        sys.exit(EXIT_DENIED)
    except KeyError as exc:
        msg = exc.args[0] if exc.args else exc
        hint = ""
        if getattr(args, "db", None):
            hint = (
                f" (database: {args.db}. Load the workbook into it first with "
                f"`kccs-evidence ingest --workbook <file> --db {args.db}`.)"
            )
        print(f"NOT FOUND: {msg}{hint}", file=sys.stderr)
        sys.exit(EXIT_NOT_FOUND)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(EXIT_INVALID)


if __name__ == "__main__":
    main()
