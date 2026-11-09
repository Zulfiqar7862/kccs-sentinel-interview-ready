"""Health, readiness, metrics, system info and workbook ingest."""

from __future__ import annotations

from datetime import UTC
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ....application.access import Principal
from ....infrastructure.workbook import load_workbook_snapshot
from ..deps import ServiceDep, SettingsDep, require_role
from ..schemas import IngestRequest, IngestResult, Liveness, Problem, Readiness

router = APIRouter(tags=["system"])
AdminDep = Annotated[Principal, Depends(require_role("PLATFORM_ADMIN"))]


@router.get("/health/live", summary="Liveness: the process is up")
def live() -> Liveness:
    return Liveness(status="ok")


@router.get(
    "/health/ready",
    summary="Readiness: workbook loaded and store integrity self-check passes",
    responses={503: {"model": Readiness}},
)
def ready(service: ServiceDep, response: Response) -> Readiness:
    res = Readiness(**service.readiness())
    if not res.ready:
        response.status_code = 503
    return res


@router.get("/metrics", summary="Prometheus text metrics", response_class=Response)
def metrics(request: Request, service: ServiceDep) -> Response:
    counters: dict[tuple[str, int], int] = request.app.state.request_counter
    lines = ["# TYPE kccs_http_requests_total counter"]
    lines += [f'kccs_http_requests_total{{route="{r}",status="{s}"}} {n}' for (r, s), n in sorted(counters.items())]
    info = service.info()
    lines += [
        "# TYPE kccs_assessments_stored gauge",
        f"kccs_assessments_stored {info['assessments_stored']}",
        "# TYPE kccs_obligations_registered gauge",
        f"kccs_obligations_registered {info['obligations_registered']}",
    ]
    ready_state = service.readiness()
    lines += [
        "# TYPE kccs_ready gauge",
        f"kccs_ready {int(ready_state['ready'])}",
        "# TYPE kccs_assessments_failing_hash gauge",
        f"kccs_assessments_failing_hash {len(ready_state['assessments_failing_hash'])}",
    ]
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@router.get("/api/v1/system/info", summary="Versions, code fingerprint, config hashes, snapshots")
def info(service: ServiceDep) -> dict[str, Any]:
    return service.info()


@router.post(
    "/api/v1/ingest",
    summary="Load the workbook into the append-only store (idempotent)",
    responses={403: {"model": Problem}, 404: {"model": Problem}, 422: {"model": Problem}},
)
def ingest(body: IngestRequest, service: ServiceDep, settings: SettingsDep, _admin: AdminDep) -> IngestResult:
    path = settings.workbook if body.workbook_path is None else (settings.data_dir / body.workbook_path)
    data_root = settings.data_dir.resolve()
    if body.workbook_path is not None and data_root not in path.resolve().parents:
        raise HTTPException(422, "workbook_path must be inside KCCS_DATA_DIR")
    recorded = body.recorded_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if body.recorded_at else None
    return IngestResult(**service.ingest(load_workbook_snapshot(path), recorded))
