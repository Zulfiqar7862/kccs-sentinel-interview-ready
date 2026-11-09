"""Source records: the immutable unit of evidence, plus canonical hashing.

A SourceRecord is one row exactly as received (sheet + Excel row + payload).
A VersionedRecord adds knowledge time (`recorded_at`) and a version number,
which is what the bitemporal store returns. Hashing helpers live here because
content addressing (row hashes, assessment IDs, package digests) is a domain
rule, not a storage detail.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def row_hash(sheet: str, payload: dict[str, Any]) -> str:
    return sha256_text(canonical_json({"sheet": sheet, "payload": payload}))


@dataclass(frozen=True)
class SourceRecord:
    sheet: str
    record_key: str
    excel_row: int
    tenant_code: str | None
    attribution: str
    payload: dict[str, Any]
    row_hash: str

    @property
    def source_ref(self) -> str:
        return f"{self.sheet}!R{self.excel_row}"

    def get(self, col: str) -> Any:
        return self.payload.get(col)


@dataclass
class SourceSnapshot:
    snapshot_id: str
    file_name: str
    file_sha256: str
    extract_date: str | None
    records: list[SourceRecord] = field(default_factory=list)
    sheet_columns: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class VersionedRecord(SourceRecord):
    version: int = 1
    recorded_at: str = ""
    change_kind: str = "INGEST"
