"""API contract tests that need no workbook (they run in CI): auth, validation, errors, health, UI."""

import pytest
from fastapi.testclient import TestClient

from conftest import FIXED_NOW, synthetic_record, synthetic_store
from kccs_evidence.application.service import KernelService
from kccs_evidence.infrastructure.sqlite_store import Store
from kccs_evidence.interfaces.api.app import create_app
from kccs_evidence.interfaces.api.settings import Settings

H = {"X-Actor": "qa", "X-Tenant-Scope": "T-KAVERI"}


@pytest.fixture()
def empty_client(tmp_path):
    settings = Settings(
        db_path=tmp_path / "k.sqlite", artifacts_dir=tmp_path, autoload=False, log_format="text", log_level="WARNING"
    )
    service = KernelService(Store(":memory:"), tmp_path, lambda: FIXED_NOW)
    with TestClient(create_app(settings, service)) as c:
        yield c


@pytest.fixture()
def synthetic_client(tmp_path):
    ev = {
        "event_id": "EXC-900001",
        "tenant_code": "T-KAVERI",
        "alert_ts_utc": "2026-07-28 06:31",
        "excursion_start_utc": "2026-07-28 06:14",
        "shipment_ref": "SHP-KAV-1",
    }
    store = synthetic_store([synthetic_record("01_Excursion_Events", "EXC-900001", 2, "T-KAVERI", "TENANT", ev)])
    settings = Settings(artifacts_dir=tmp_path, autoload=False, log_format="text", log_level="WARNING")
    with TestClient(create_app(settings, KernelService(store, tmp_path, lambda: FIXED_NOW))) as c:
        yield c


def test_liveness_always_ok_and_readiness_503_before_ingest(empty_client):
    assert empty_client.get("/health/live").json() == {"status": "ok"}
    r = empty_client.get("/health/ready")
    assert r.status_code == 503 and r.json()["workbook_loaded"] is False


def test_requests_before_ingest_get_503_problem(empty_client):
    r = empty_client.get("/api/v1/tenants/T-KAVERI/events", headers=H)
    assert r.status_code == 503 and r.json()["title"] == "Not ready"


@pytest.mark.parametrize("headers", [{}, {"X-Actor": "qa"}, {"X-Tenant-Scope": "T-KAVERI"}])
def test_missing_identity_is_401(empty_client, headers):
    r = empty_client.get("/api/v1/tenants/T-KAVERI/events", headers=headers)
    assert r.status_code == 401 and r.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Actor": "qa", "X-Tenant-Scope": "kaveri"},
        {"X-Actor": "qa;drop", "X-Tenant-Scope": "T-KAVERI"},
        {"X-Actor": "qa", "X-Tenant-Scope": "T-KAVERI", "X-Roles": "GOD"},
    ],
)
def test_malformed_identity_is_422(empty_client, headers):
    assert empty_client.get("/api/v1/tenants/T-KAVERI/events", headers=headers).status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/tenants/kaveri/events",
        "/api/v1/tenants/T-KAVERI/events/107133",
        "/api/v1/assessments/ASM-XYZ",
        "/api/v1/tenants/T-KAVERI/events?limit=0",
    ],
)
def test_path_and_query_validation(empty_client, path):
    r = empty_client.get(path, headers=H)
    assert r.status_code == 422 and r.json()["title"] == "Validation failed"


def test_assess_body_validation(synthetic_client):
    url = "/api/v1/tenants/T-KAVERI/events/EXC-900001/assessments"
    assert synthetic_client.post(url, headers=H, json={"knowledge_cutoff": "yesterday"}).status_code == 422
    assert synthetic_client.post(url, headers=H, json={"knowledge_cutoff": "2026-07-28T07:00:00"}).status_code == 422
    assert synthetic_client.post(url, headers=H, json={"mode": "FAST"}).status_code == 422
    assert synthetic_client.post(url, headers=H, json={"surprise": 1}).status_code == 422


def test_synthetic_event_is_served_without_outcome_fields(synthetic_client):
    r = synthetic_client.get("/api/v1/tenants/T-KAVERI/events/EXC-900001", headers=H)
    assert r.status_code == 200 and r.json()["fields"]["event_id"] == "EXC-900001"
    other = synthetic_client.get(
        "/api/v1/tenants/T-KAVERI/events/EXC-900001", headers={"X-Actor": "p", "X-Tenant-Scope": "T-PINNACLE"}
    )
    assert other.status_code == 403


def test_request_id_is_echoed(empty_client):
    r = empty_client.get("/health/live", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"


def test_openapi_and_ui_are_served(empty_client):
    spec = empty_client.get("/openapi.json").json()
    for p in (
        "/api/v1/tenants/{tenant}/events/{event_id}/assessments",
        "/api/v1/obligations/queue",
        "/api/v1/assessments/{assessment_id}/package",
        "/health/ready",
    ):
        assert p in spec["paths"]
    ui = empty_client.get("/ui/")
    assert ui.status_code == 200 and "KCCS Sentinel" in ui.text
    assert empty_client.get("/ui/app.js").status_code == 200
    assert empty_client.get("/", follow_redirects=False).status_code in (307, 302)
