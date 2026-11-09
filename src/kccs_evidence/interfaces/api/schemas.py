"""Request and response models (the public API contract, published as OpenAPI)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from ...domain.temporal import parse_iso_utc

ObligationState = Literal[
    "OPEN_UNDETERMINED",
    "NOTIFIABLE_CONFIRMED",
    "SUBMISSION_QUEUED",
    "SUBMITTED_AWAITING_ACK",
    "DELIVERY_FAILED",
    "ACKNOWLEDGED",
    "CLOSED_NOT_NOTIFIABLE",
]


class Problem(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    request_id: str | None = None
    errors: list[dict[str, Any]] | None = None


class Liveness(BaseModel):
    status: Literal["ok"]


class Readiness(BaseModel):
    ready: bool
    workbook_loaded: bool
    append_only_triggers: bool
    missing_triggers: list[str]
    assessments_checked: int
    assessments_failing_hash: list[str]


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workbook_path: str | None = Field(None, description="Path inside KCCS_DATA_DIR; default KCCS_WORKBOOK")
    recorded_at: AwareDatetime | None = Field(
        None, description="Knowledge time for this snapshot; default extract date"
    )


class IngestResult(BaseModel):
    snapshot_id: str
    file_sha256: str
    recorded_at: str
    new_records: int
    new_versions: int
    unchanged: int


class EventList(BaseModel):
    tenant: str
    total: int
    limit: int
    offset: int
    items: list[dict[str, Any]]


class EventDetail(BaseModel):
    source_ref: str
    version: int
    recorded_at: str
    fields: dict[str, Any]


class AssessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    knowledge_cutoff: str = Field("alert", description="alert | extract | now | ISO-8601 UTC timestamp", max_length=40)
    mode: Literal["RECONSTRUCTED", "STRICT"] = "RECONSTRUCTED"

    @field_validator("knowledge_cutoff")
    @classmethod
    def _cutoff(cls, v: str) -> str:
        if v in {"alert", "extract", "now"}:
            return v
        parse_iso_utc(v)  # raises ValueError -> 422 if not an aware ISO timestamp
        return v


class AssessmentEnvelope(BaseModel):
    stored: Literal["new", "existing"]
    assessment_id: str
    status: str
    assessment: dict[str, Any]


class AssessmentHistoryItem(BaseModel):
    assessment_id: str
    knowledge_cutoff: str
    first_stored_at: str
    supersedes: str | None
    status: str
    blocking_reasons: list[str]


class Verification(BaseModel):
    package: str
    ok: bool
    problems: list[str]
    package_digest: str


class PackageExport(BaseModel):
    manifest: dict[str, Any]
    verification: Verification


class TamperDemo(BaseModel):
    original: Verification
    tampered_copy: Verification
    edit: str


class ObligationOut(BaseModel):
    obligation_id: str
    tenant_code: str
    event_id: str
    clock_start_utc: str
    due_at_utc: str | None
    regime_kind: str
    state: str
    version: int
    satisfied: bool
    hours_remaining: float | None
    breached: bool
    escalate_now: bool
    history: list[dict[str, Any]]


class ObligationQueue(BaseModel):
    as_of_utc: str
    margin_hours: float
    only_at_risk: bool
    count: int
    items: list[ObligationOut]


class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to_state: ObligationState
    expected_version: int = Field(ge=1, description="Optimistic lock: the version you last read")
    note: str = Field("", max_length=2000)


class TransitionResult(BaseModel):
    applied: bool
    obligation: ObligationOut


class CorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sheet: Literal["02_Product_Master", "05_SOP_Index", "06_Stability_Index"]
    record_key: str = Field(min_length=1, max_length=80)
    set: dict[str, str | int | float | None] = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=5, max_length=500)
    recorded_at: AwareDatetime


class CorrectionResult(BaseModel):
    sheet: str
    record_key: str
    new_version: int
    recorded_at: str


class AuditEvent(BaseModel):
    seq: int
    at: str
    actor: str
    tenant_code: str | None
    action: str
    target: str | None
    outcome: str
    detail_json: str | None
