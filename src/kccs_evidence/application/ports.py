"""Ports the application layer needs from infrastructure (implemented by SqliteStore).

Production would implement the same protocol on Postgres; nothing in the
application or domain layers imports a concrete store.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..domain.records import SourceSnapshot, VersionedRecord


class EvidenceStore(Protocol):
    def ingest_snapshot(self, snap: SourceSnapshot, recorded_at: str) -> dict[str, int]: ...

    def apply_correction(
        self, sheet: str, record_key: str, changes: dict[str, Any], recorded_at: str, actor: str, reason: str
    ) -> int: ...

    def records(
        self, sheet: str, *, tenant: str | None = None, shared: bool = False, as_known_at: str | None = None
    ) -> list[VersionedRecord]: ...

    def record_history(self, sheet: str, key: str) -> list[VersionedRecord]: ...

    def snapshots(self) -> list[dict[str, Any]]: ...

    def mappings(self, kind: str, tenant: str | None, as_known_at: str | None) -> list[dict[str, Any]]: ...

    def put_assessment(self, payload: dict[str, Any], stored_at: str) -> tuple[str, bool]: ...

    def get_assessment_row(self, assessment_id: str) -> Any: ...

    def assessments_for_event(self, tenant: str, event_id: str) -> list[dict[str, Any]]: ...

    def count_assessments(self) -> int: ...

    def audit(
        self,
        *,
        at: str,
        actor: str,
        tenant: str | None,
        action: str,
        target: str | None,
        outcome: str,
        detail: dict[str, Any] | None = None,
    ) -> None: ...

    def audit_events(self, action: str | None = None) -> list[dict[str, Any]]: ...

    def tenant_codes(self) -> list[str]: ...

    def integrity_check(self) -> dict[str, Any]: ...

    def append_obligation_transition(
        self,
        *,
        tenant: str,
        event_id: str,
        from_state: str,
        to_state: str,
        expected_version: int,
        at: str,
        actor: str,
        note: str,
        idempotency_key: str | None,
    ) -> None: ...

    def obligation_transitions(self) -> list[dict[str, Any]]: ...

    def obligation_transition_by_key(self, idempotency_key: str) -> dict[str, Any] | None: ...
