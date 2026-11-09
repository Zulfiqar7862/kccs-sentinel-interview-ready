"""Application service (use-case facade) shared by the REST API and the CLI.

Every use case takes a `Principal` first and opens a `TenantView` before it
reads evidence, so tenant isolation is enforced in one place for every
interface. The service is the only place that holds a lock: SQLite allows one
writer, and the prototype API runs request handlers in a thread pool.
"""

from __future__ import annotations

import io
import json
import shutil
import threading
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .. import ASSESSMENT_SCHEMA_VERSION, RULESET_VERSION, STORE_SCHEMA_VERSION, __version__
from ..config.loader import config_manifest, load_config
from ..domain.obligations import IllegalTransition, Obligation, ObligationLedger, Regime
from ..domain.records import SourceSnapshot
from ..domain.temporal import iso, parse_pack_utc
from .access import Principal, TenantAccessDenied, TenantView
from .assessment import ALLOWED_EVENT_FIELDS, assess_and_store, code_fingerprint
from .package import export_package, verify_package
from .ports import EvidenceStore

Clock = Callable[[], datetime]
EVENTS = "01_Excursion_Events"
PACK_EXTRACT_CUTOFF = "2026-09-14T23:59:00Z"
CUTOFF_ALIASES = {"extract": PACK_EXTRACT_CUTOFF}
CORRECTABLE_SHEETS = {"02_Product_Master", "05_SOP_Index", "06_Stability_Index"}


class NotReady(RuntimeError):
    """No workbook has been ingested yet."""


@dataclass(frozen=True)
class EventPage:
    total: int
    items: list[dict[str, Any]]


def obligation_view(ob: Obligation, now: datetime) -> dict[str, Any]:
    remaining = None if ob.due_at is None else round((ob.due_at - now).total_seconds() / 3600, 2)
    return {
        "obligation_id": ob.obligation_id,
        "tenant_code": ob.tenant,
        "event_id": ob.event_id,
        "clock_start_utc": iso(ob.clock_start),
        "due_at_utc": iso(ob.due_at) if ob.due_at else None,
        "regime_kind": ob.regime_kind,
        "state": ob.state,
        "version": ob.version,
        "satisfied": ob.satisfied,
        "hours_remaining": remaining,
        "breached": bool(ob.due_at and not ob.satisfied and now > ob.due_at),
        "escalate_now": ob.due_at is None and not ob.satisfied,
        "history": ob.history,
    }


class KernelService:
    def __init__(self, store: EvidenceStore, artifacts_dir: Path, clock: Clock) -> None:
        self.store = store
        self.artifacts_dir = Path(artifacts_dir)
        self.clock = clock
        self._lock = threading.RLock()
        self.ledger = ObligationLedger()
        self._rebuild_ledger()

    # ------------------------------------------------------------------ system
    def info(self) -> dict[str, Any]:
        with self._lock:
            return {
                "kernel_version": __version__,
                "ruleset_version": RULESET_VERSION,
                "assessment_schema_version": ASSESSMENT_SCHEMA_VERSION,
                "store_schema_version": STORE_SCHEMA_VERSION,
                "code_sha256": code_fingerprint(),
                "config": config_manifest(),
                "snapshots": self.store.snapshots(),
                "tenants": self.store.tenant_codes(),
                "assessments_stored": self.store.count_assessments(),
                "obligations_registered": len(self.ledger.all()),
                "model": {"route": "NONE", "reason": "deterministic kernel; no language model is called"},
            }

    def readiness(self) -> dict[str, Any]:
        with self._lock:
            integrity = self.store.integrity_check()
            loaded = bool(self.store.snapshots())
            ok = loaded and integrity["append_only_triggers"] and not integrity["assessments_failing_hash"]
            return {"ready": ok, "workbook_loaded": loaded, **integrity}

    def ingest(self, snap: SourceSnapshot, recorded_at: str | None = None) -> dict[str, Any]:
        recorded = recorded_at or f"{snap.extract_date}T00:00:00Z"
        with self._lock:
            stats = self.store.ingest_snapshot(snap, recorded)
            self._rebuild_ledger()
        return {"snapshot_id": snap.snapshot_id, "file_sha256": snap.file_sha256, "recorded_at": recorded, **stats}

    def _require_loaded(self) -> None:
        if not self.store.snapshots():
            raise NotReady("no workbook ingested yet: POST /api/v1/ingest or run `kccs-evidence ingest`")

    # ------------------------------------------------------------------ events
    def list_tenants(self, principal: Principal) -> list[str]:
        with self._lock:
            return [t for t in self.store.tenant_codes() if t in principal.tenants]

    def list_events(
        self, principal: Principal, tenant: str, *, limit: int, offset: int, query: str | None
    ) -> EventPage:
        with self._lock:
            self._require_loaded()
            view = TenantView(self.store, principal, tenant, clock=self.clock)
            rows = view.tenant_records(EVENTS)
            if query:
                q = query.casefold()
                rows = [r for r in rows if any(q in str(r.get(k) or "").casefold() for k in ALLOWED_EVENT_FIELDS)]
            items = []
            for r in rows[offset : offset + limit]:
                latest = self.store.assessments_for_event(tenant, r.record_key)
                item = {k: r.get(k) for k in ALLOWED_EVENT_FIELDS}
                item["source_ref"] = r.source_ref
                item["latest_assessment"] = (
                    {
                        "assessment_id": latest[-1]["assessment_id"],
                        "status": json.loads(latest[-1]["payload_json"])["disposition_evidence_status"],
                    }
                    if latest
                    else None
                )
                items.append(item)
            return EventPage(total=len(rows), items=items)

    def get_event(self, principal: Principal, tenant: str, event_id: str) -> dict[str, Any]:
        """Only the fields that exist at alert receipt; outcome columns are never served."""
        with self._lock:
            self._require_loaded()
            rec = TenantView(self.store, principal, tenant, clock=self.clock).event(event_id)
            return {
                "source_ref": rec.source_ref,
                "version": rec.version,
                "recorded_at": rec.recorded_at,
                "fields": {k: rec.get(k) for k in ALLOWED_EVENT_FIELDS},
            }

    # ------------------------------------------------------------------ assessments
    def assess(
        self,
        principal: Principal,
        tenant: str,
        event_id: str,
        *,
        knowledge_cutoff: str = "alert",
        mode: str = "RECONSTRUCTED",
    ) -> tuple[dict[str, Any], bool]:
        cutoff = CUTOFF_ALIASES.get(knowledge_cutoff, knowledge_cutoff)
        with self._lock:
            self._require_loaded()
            return assess_and_store(
                self.store, principal, tenant, event_id, knowledge_cutoff=cutoff, mode=mode, clock=self.clock
            )

    def assessment_history(self, principal: Principal, tenant: str, event_id: str) -> list[dict[str, Any]]:
        with self._lock:
            TenantView(self.store, principal, tenant, clock=self.clock).event(event_id)
            out = []
            for row in self.store.assessments_for_event(tenant, event_id):
                p = json.loads(row["payload_json"])
                out.append(
                    {
                        "assessment_id": row["assessment_id"],
                        "knowledge_cutoff": row["knowledge_cutoff"],
                        "first_stored_at": row["first_stored_at"],
                        "supersedes": row["supersedes"],
                        "status": p["disposition_evidence_status"],
                        "blocking_reasons": p["blocking_reasons"],
                    }
                )
            return out

    def get_assessment(self, principal: Principal, assessment_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._authorised_assessment_row(principal, assessment_id, "ASSESSMENT_READ")
            payload: dict[str, Any] = json.loads(row["payload_json"])
            return payload

    def _authorised_assessment_row(self, principal: Principal, assessment_id: str, action: str) -> Any:
        row = self.store.get_assessment_row(assessment_id)
        if row is None:
            raise KeyError(f"assessment {assessment_id} not found")
        if row["tenant_code"] not in principal.tenants:
            self.store.audit(
                at=iso(self.clock()),
                actor=principal.actor_id,
                tenant=row["tenant_code"],
                action=action,
                target=assessment_id,
                outcome="DENIED",
            )
            raise TenantAccessDenied(f"{principal.actor_id} may not read {assessment_id}")
        return row

    # ------------------------------------------------------------------ evidence packages
    def _package_dir(self, assessment_id: str) -> Path:
        return self.artifacts_dir / "packages" / assessment_id

    def export_package(self, principal: Principal, assessment_id: str) -> dict[str, Any]:
        with self._lock:
            out = export_package(
                self.store, principal, assessment_id, self.artifacts_dir / "packages", iso(self.clock())
            )
            manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
            return {"manifest": manifest, "verification": verify_package(out)}

    def verify_package(self, principal: Principal, assessment_id: str) -> dict[str, Any]:
        with self._lock:
            self._authorised_assessment_row(principal, assessment_id, "PACKAGE_VERIFY")
            pkg = self._package_dir(assessment_id)
            if not (pkg / "MANIFEST.json").exists():
                raise KeyError(f"package for {assessment_id} has not been exported yet")
            return verify_package(pkg)

    def package_zip(self, principal: Principal, assessment_id: str) -> bytes:
        with self._lock:
            self._authorised_assessment_row(principal, assessment_id, "PACKAGE_DOWNLOAD")
            pkg = self._package_dir(assessment_id)
            if not (pkg / "MANIFEST.json").exists():
                self.export_package(principal, assessment_id)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in sorted(pkg.iterdir()):
                    zf.write(f, f"{assessment_id}/{f.name}")
            return buf.getvalue()

    def tamper_demo(self, principal: Principal, assessment_id: str) -> dict[str, Any]:
        """Copy the package, flip the status inside the copy, and show that verification fails. Demo only."""
        with self._lock:
            self._authorised_assessment_row(principal, assessment_id, "PACKAGE_TAMPER_DEMO")
            pkg = self._package_dir(assessment_id)
            if not (pkg / "MANIFEST.json").exists():
                self.export_package(principal, assessment_id)
            copy = self.artifacts_dir / "tamper_demo" / assessment_id
            if copy.exists():
                shutil.rmtree(copy)
            shutil.copytree(pkg, copy)
            target = copy / "assessment.json"
            text = target.read_text(encoding="utf-8")
            target.write_text(
                text.replace("ABSTAIN_BLOCKING_EVIDENCE_GAPS", "READY_FOR_QA_REVIEW").replace(
                    '"is_disposition": false', '"is_disposition": true'
                ),
                encoding="utf-8",
            )
            return {
                "original": verify_package(pkg),
                "tampered_copy": verify_package(copy),
                "edit": "status rewritten to READY_FOR_QA_REVIEW in the copy only",
            }

    # ------------------------------------------------------------------ notification obligations
    def _rebuild_ledger(self) -> None:
        """Register one obligation per alert (clock = alert receipt), then replay the persisted transition log."""
        ledger = ObligationLedger()
        regimes = load_config("reference_facts.json")["notification_regimes"]
        for tenant in self.store.tenant_codes():
            cfg = regimes.get(tenant)
            regime = Regime.from_config(cfg) if isinstance(cfg, dict) else Regime(kind="REGIME_UNKNOWN")
            for e in self.store.records(EVENTS, tenant=tenant):
                ledger.register(tenant, e.record_key, parse_pack_utc(e.get("alert_ts_utc")), regime)
        for tr in self.store.obligation_transitions():
            ledger.transition(
                tr["tenant_code"],
                tr["event_id"],
                tr["to_state"],
                at=datetime.fromisoformat(tr["at"].replace("Z", "+00:00")),
                by=tr["actor"],
                expected_version=tr["expected_version"],
                note=tr["note"] or "",
            )
        self.ledger = ledger

    def obligations(
        self,
        principal: Principal,
        *,
        tenant: str | None,
        now: datetime,
        margin_hours: float,
        only_at_risk: bool,
        received_within_hours: float | None = None,
    ) -> list[dict[str, Any]]:
        """Queue as of `now`: only alerts already received by then (no future leakage), deadline first."""
        with self._lock:
            self._require_loaded()
            scope = {tenant} if tenant else set(principal.tenants)
            if tenant:
                TenantView(self.store, principal, tenant, clock=self.clock)  # access check + audit
            obs = (
                self.ledger.at_risk(now, timedelta(hours=margin_hours))
                if only_at_risk
                else sorted(self.ledger.all(), key=lambda o: (o.due_at is not None, o.due_at or now))
            )
            earliest = now - timedelta(hours=received_within_hours) if received_within_hours is not None else None
            return [
                obligation_view(o, now)
                for o in obs
                if o.tenant in scope
                and o.tenant in principal.tenants
                and o.clock_start <= now
                and (earliest is None or o.clock_start >= earliest)
            ]

    def transition_obligation(
        self,
        principal: Principal,
        tenant: str,
        event_id: str,
        *,
        to_state: str,
        expected_version: int,
        note: str,
        idempotency_key: str | None,
    ) -> tuple[dict[str, Any], bool]:
        """Apply a state change. Returns (obligation, applied). A repeated Idempotency-Key returns the current state."""
        with self._lock:
            TenantView(self.store, principal, tenant, clock=self.clock).event(event_id)
            if idempotency_key:
                prior = self.store.obligation_transition_by_key(idempotency_key)
                if prior is not None:
                    if (prior["tenant_code"], prior["event_id"], prior["to_state"]) != (tenant, event_id, to_state):
                        raise IllegalTransition("Idempotency-Key reused for a different request")
                    ob = self.ledger.get(tenant, event_id)
                    return obligation_view(ob, self.clock()), False
            current = self.ledger.get(tenant, event_id)
            from_state, at = current.state, self.clock()
            ob = self.ledger.transition(
                tenant, event_id, to_state, at=at, by=principal.actor_id, expected_version=expected_version, note=note
            )
            self.store.append_obligation_transition(
                tenant=tenant,
                event_id=event_id,
                from_state=from_state,
                to_state=to_state,
                expected_version=expected_version,
                at=iso(at),
                actor=principal.actor_id,
                note=note,
                idempotency_key=idempotency_key,
            )
            self.store.audit(
                at=iso(at),
                actor=principal.actor_id,
                tenant=tenant,
                action="OBLIGATION_TRANSITION",
                target=event_id,
                outcome="APPLIED",
                detail={"from": from_state, "to": to_state},
            )
            return obligation_view(ob, at), True

    # ------------------------------------------------------------------ corrections and audit
    def correct(
        self,
        principal: Principal,
        tenant: str,
        *,
        sheet: str,
        record_key: str,
        changes: dict[str, Any],
        reason: str,
        recorded_at: str,
    ) -> dict[str, Any]:
        if sheet not in CORRECTABLE_SHEETS:
            raise ValueError(f"corrections are allowed only on {sorted(CORRECTABLE_SHEETS)}")
        with self._lock:
            view = TenantView(self.store, principal, tenant, clock=self.clock)
            if not any(r.record_key == record_key for r in view.tenant_records(sheet)):
                raise KeyError(f"{sheet}/{record_key} not found for tenant {tenant}")
            version = self.store.apply_correction(sheet, record_key, changes, recorded_at, principal.actor_id, reason)
            self.store.audit(
                at=iso(self.clock()),
                actor=principal.actor_id,
                tenant=tenant,
                action="SOURCE_CORRECTION",
                target=f"{sheet}/{record_key}",
                outcome="APPENDED",
                detail={"version": version, "reason": reason},
            )
            return {"sheet": sheet, "record_key": record_key, "new_version": version, "recorded_at": recorded_at}

    def audit_trail(self, principal: Principal, tenant: str, *, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            if tenant not in principal.tenants:
                TenantView(self.store, principal, tenant, clock=self.clock)  # raises + audits
            rows = [a for a in self.store.audit_events() if a["tenant_code"] == tenant]
            return rows[-limit:]
