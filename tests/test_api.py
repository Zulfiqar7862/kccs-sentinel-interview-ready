"""REST API end to end on the real workbook (skipped when the workbook is absent)."""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from conftest import FIXED_NOW, WORKBOOK
from kccs_evidence.application.assessment import OUTCOME_FIELDS
from kccs_evidence.interfaces.api.app import create_app
from kccs_evidence.interfaces.api.settings import Settings

KAV = {"X-Actor": "qa-kaveri", "X-Tenant-Scope": "T-KAVERI"}
KAV_ALL = {**KAV, "X-Roles": "QA_REVIEWER,QA_DATA_STEWARD,REGULATORY_AFFAIRS"}
PIN = {"X-Actor": "qa-pinnacle", "X-Tenant-Scope": "T-PINNACLE"}
ADMIN = {"X-Actor": "ops", "X-Tenant-Scope": "T-KAVERI", "X-Roles": "PLATFORM_ADMIN"}


def _settings(tmp, **kw) -> Settings:
    base = {
        "db_path": tmp / "k.sqlite",
        "artifacts_dir": tmp / "art",
        "data_dir": WORKBOOK.parent,
        "workbook": WORKBOOK,
        "autoload": True,
        "fixed_now": FIXED_NOW,
        "log_format": "text",
        "log_level": "WARNING",
    }
    base.update(kw)
    return Settings(**base)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    if not WORKBOOK.exists():
        pytest.skip(f"workbook not found at {WORKBOOK}")
    tmp = tmp_path_factory.mktemp("api")
    with TestClient(create_app(_settings(tmp))) as c:
        c.tmp = tmp
        yield c


def test_ready_after_autoload(client):
    r = client.get("/health/ready")
    assert r.status_code == 200 and r.json()["ready"] is True and r.json()["append_only_triggers"] is True


def test_event_list_is_tenant_scoped_and_never_serves_outcomes(client):
    r = client.get("/api/v1/tenants/T-KAVERI/events?limit=500", headers=KAV)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == len(body["items"]) > 0
    assert all(e["tenant_code"] == "T-KAVERI" for e in body["items"])
    leaked = {k for e in body["items"] for k in e} & set(OUTCOME_FIELDS)
    assert not leaked


def test_brief_case_assessment_is_idempotent_and_abstains(client):
    url = "/api/v1/tenants/T-KAVERI/events/EXC-107133/assessments"
    first = client.post(url, headers=KAV, json={"knowledge_cutoff": "alert"})
    again = client.post(url, headers=KAV, json={"knowledge_cutoff": "alert"})
    assert first.status_code == 201 and again.status_code == 200
    a = first.json()["assessment"]
    assert first.json()["assessment_id"] == again.json()["assessment_id"] == a["assessment_id"]
    assert first.headers["Location"].endswith(a["assessment_id"])
    assert a["disposition_evidence_status"] == "ABSTAIN_BLOCKING_EVIDENCE_GAPS" and a["is_disposition"] is False
    assert a["entities"]["product"]["resolved_id"] == "02_Product_Master!R57"
    assert a["evidence"]["sop_origin"][0]["in_force"] == ["Rev 02", "Rev 03"]
    assert a["notification_track"]["due_at_utc"] == "2026-08-12T06:31:00Z"
    assert client.get(f"/api/v1/assessments/{a['assessment_id']}", headers=KAV).json() == json.loads(json.dumps(a))


def test_later_knowledge_cutoff_supersedes(client):
    url = "/api/v1/tenants/T-KAVERI/events/EXC-107133/assessments"
    a1 = client.post(url, headers=KAV, json={"knowledge_cutoff": "alert"}).json()["assessment_id"]
    a2 = client.post(url, headers=KAV, json={"knowledge_cutoff": "extract"}).json()
    assert a2["assessment_id"] != a1
    hist = client.get(url, headers=KAV).json()
    assert [h["assessment_id"] for h in hist][:2] == [a1, a2["assessment_id"]]
    assert hist[1]["supersedes"] == a1


def test_cross_tenant_reads_are_denied_and_audited(client):
    r = client.get("/api/v1/tenants/T-KAVERI/events/EXC-107133", headers=PIN)
    assert r.status_code == 403 and r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["title"] == "Access denied" and r.json()["request_id"]
    aid = client.post("/api/v1/tenants/T-KAVERI/events/EXC-107133/assessments", headers=KAV, json={}).json()[
        "assessment_id"
    ]
    assert client.get(f"/api/v1/assessments/{aid}", headers=PIN).status_code == 403
    assert client.post(f"/api/v1/assessments/{aid}/package", headers=PIN).status_code == 403
    audit = client.get("/api/v1/tenants/T-KAVERI/audit", headers=KAV).json()
    assert any(a["outcome"] == "DENIED" and a["actor"] == "qa-pinnacle" for a in audit)


def test_unknown_event_is_not_found_without_revealing_other_tenants(client):
    meridian_event = client.get(
        "/api/v1/tenants/T-MERIDIAN/events?limit=1", headers={"X-Actor": "m", "X-Tenant-Scope": "T-MERIDIAN"}
    ).json()["items"][0]["event_id"]
    r = client.get(f"/api/v1/tenants/T-KAVERI/events/{meridian_event}", headers=KAV)
    assert r.status_code == 404


def test_package_export_verify_zip_and_tamper_detection(client):
    aid = client.post("/api/v1/tenants/T-KAVERI/events/EXC-107133/assessments", headers=KAV, json={}).json()[
        "assessment_id"
    ]
    exp = client.post(f"/api/v1/assessments/{aid}/package", headers=KAV)
    assert exp.status_code == 201 and exp.json()["verification"]["ok"] is True
    assert client.get(f"/api/v1/assessments/{aid}/package/verify", headers=KAV).json()["ok"] is True
    z = client.get(f"/api/v1/assessments/{aid}/package.zip", headers=KAV)
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert z.headers["content-type"] == "application/zip" and f"{aid}/MANIFEST.json" in names
    t = client.post(f"/api/v1/assessments/{aid}/package/tamper-demo", headers=KAV).json()
    assert t["original"]["ok"] is True and t["tampered_copy"]["ok"] is False
    assert "hash mismatch assessment.json" in t["tampered_copy"]["problems"]


def test_obligation_queue_orders_by_deadline_and_escalates_incomplete_policy(client):
    r = client.get(
        "/api/v1/obligations/queue?as_of=2026-07-29T00:00:00Z&margin_hours=720",
        headers={"X-Actor": "ra", "X-Tenant-Scope": "T-KAVERI,T-PINNACLE"},
    )
    items = r.json()["items"]
    assert items, "expected obligations in the window"
    no_deadline = [i for i in items if i["due_at_utc"] is None]
    assert all(i["escalate_now"] for i in no_deadline)
    assert items[: len(no_deadline)] == no_deadline  # incomplete policy first
    dues = [i["due_at_utc"] for i in items if i["due_at_utc"]]
    assert dues == sorted(dues)
    kav = client.get("/api/v1/tenants/T-KAVERI/obligations?as_of=2026-07-29T00:00:00Z", headers=KAV).json()["items"]
    ob = next(i for i in kav if i["event_id"] == "EXC-107133")
    assert ob["due_at_utc"] == "2026-08-12T06:31:00Z" and ob["clock_start_utc"] == "2026-07-28T06:31:00Z"


def test_obligation_state_machine_guards(client):
    base = "/api/v1/tenants/T-KAVERI/obligations/EXC-107133/transitions"
    assert (
        client.post(base, headers=KAV, json={"to_state": "NOTIFIABLE_CONFIRMED", "expected_version": 1}).status_code
        == 403
    )
    illegal = client.post(base, headers=KAV_ALL, json={"to_state": "ACKNOWLEDGED", "expected_version": 1})
    assert illegal.status_code == 409
    no_reason = client.post(base, headers=KAV_ALL, json={"to_state": "CLOSED_NOT_NOTIFIABLE", "expected_version": 1})
    assert no_reason.status_code == 409
    hdr = {**KAV_ALL, "Idempotency-Key": "k-107133-1"}
    ok = client.post(
        base, headers=hdr, json={"to_state": "NOTIFIABLE_CONFIRMED", "expected_version": 1, "note": "RA call"}
    )
    assert ok.status_code == 200 and ok.json()["applied"] is True and ok.json()["obligation"]["version"] == 2
    replay = client.post(
        base, headers=hdr, json={"to_state": "NOTIFIABLE_CONFIRMED", "expected_version": 1, "note": "RA call"}
    )
    assert replay.json()["applied"] is False and replay.headers["Idempotent-Replay"] == "true"
    stale = client.post(base, headers=KAV_ALL, json={"to_state": "SUBMISSION_QUEUED", "expected_version": 1})
    assert stale.status_code == 409 and "version conflict" in stale.json()["detail"]
    bad = client.post(base, headers=KAV_ALL, json={"to_state": "NOT_A_STATE", "expected_version": 2})
    assert bad.status_code == 422 and bad.json()["errors"]


def test_obligation_transitions_survive_restart(client):
    base = "/api/v1/tenants/T-KAVERI/obligations/EXC-107133/transitions"
    cur = next(
        i
        for i in client.get("/api/v1/tenants/T-KAVERI/obligations", headers=KAV).json()["items"]
        if i["event_id"] == "EXC-107133"
    )
    if cur["state"] == "OPEN_UNDETERMINED":
        client.post(
            base, headers=KAV_ALL, json={"to_state": "NOTIFIABLE_CONFIRMED", "expected_version": 1, "note": "x"}
        )
        cur = next(
            i
            for i in client.get("/api/v1/tenants/T-KAVERI/obligations", headers=KAV).json()["items"]
            if i["event_id"] == "EXC-107133"
        )
    with TestClient(create_app(_settings(client.tmp))) as c2:
        again = next(
            i
            for i in c2.get("/api/v1/tenants/T-KAVERI/obligations", headers=KAV).json()["items"]
            if i["event_id"] == "EXC-107133"
        )
    assert (again["state"], again["version"]) == (cur["state"], cur["version"])


def test_correction_is_appended_and_produces_a_new_assessment(client):
    url = "/api/v1/tenants/T-KAVERI/events/EXC-107133/assessments"
    before = client.post(url, headers=KAV, json={"knowledge_cutoff": "2026-09-21T00:00:00Z"}).json()
    products = client.get("/api/v1/tenants/T-KAVERI/events/EXC-107133", headers=KAV)
    assert products.status_code == 200
    body = {
        "sheet": "02_Product_Master",
        "record_key": "R57",
        "set": {"stability_study_ref": "STB-2738"},
        "reason": "SIMULATED test correction",
        "recorded_at": "2026-09-20T10:00:00Z",
    }
    assert client.post("/api/v1/tenants/T-KAVERI/corrections", headers=KAV, json=body).status_code == 403  # role
    r = client.post("/api/v1/tenants/T-KAVERI/corrections", headers=KAV_ALL, json=body)
    assert r.status_code == 201 and r.json()["new_version"] == 2
    after = client.post(url, headers=KAV, json={"knowledge_cutoff": "2026-09-21T00:00:00Z"}).json()
    assert after["assessment_id"] != before["assessment_id"]
    assert after["assessment"]["supersedes"] == before["assessment_id"]
    assert client.get(f"/api/v1/assessments/{before['assessment_id']}", headers=KAV).json() == before["assessment"]
    naive = {**body, "recorded_at": "2026-09-20T10:00:00"}
    assert client.post("/api/v1/tenants/T-KAVERI/corrections", headers=KAV_ALL, json=naive).status_code == 422


def test_ingest_requires_admin_and_is_idempotent(client):
    assert client.post("/api/v1/ingest", headers=KAV, json={}).status_code == 403
    r = client.post("/api/v1/ingest", headers=ADMIN, json={})
    assert r.status_code == 200 and r.json()["new_records"] == 0
    assert client.post("/api/v1/ingest", headers=ADMIN, json={"workbook_path": "../../etc/passwd"}).status_code == 422


def test_metrics_and_system_info(client):
    m = client.get("/metrics").text
    assert "kccs_ready 1" in m and "kccs_assessments_failing_hash 0" in m
    info = client.get("/api/v1/system/info").json()
    assert info["model"]["route"] == "NONE" and "T-KAVERI" in info["tenants"]
