"""Ports (interfaces) that the domain rules depend on.

The domain never talks to a database. It reads evidence through an
`EvidenceReader`, which the application layer implements with a
tenant-scoped `TenantView`. This keeps tenant isolation outside the rules and
makes every rule testable with a fake reader.
"""

from __future__ import annotations

from typing import Any, Protocol

from .records import VersionedRecord


class EvidenceReader(Protocol):
    """Read-only, already tenant-filtered, knowledge-time-bounded evidence."""

    tenant: str

    def tenant_records(self, sheet: str) -> list[VersionedRecord]: ...

    def shared_records(self, sheet: str) -> list[VersionedRecord]: ...

    def alias_observations(self, kind: str) -> list[VersionedRecord]: ...

    def mappings(self, kind: str) -> list[dict[str, Any]]: ...
