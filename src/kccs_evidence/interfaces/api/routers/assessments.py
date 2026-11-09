"""Assessments by id, evidence packages and the tamper-detection demo."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response

from ..deps import AssessmentPath, PrincipalDep, ServiceDep, SettingsDep
from ..schemas import PackageExport, Problem, TamperDemo, Verification

router = APIRouter(
    prefix="/api/v1/assessments/{assessment_id}",
    tags=["assessments & evidence packages"],
    responses={401: {"model": Problem}, 403: {"model": Problem}, 404: {"model": Problem}},
)


@router.get("", summary="Stored assessment payload (immutable)")
def get_assessment(assessment_id: AssessmentPath, principal: PrincipalDep, service: ServiceDep) -> dict[str, Any]:
    return service.get_assessment(principal, assessment_id)


@router.post("/package", status_code=201, summary="Export the hashed evidence package")
def export(assessment_id: AssessmentPath, principal: PrincipalDep, service: ServiceDep) -> PackageExport:
    return PackageExport(**service.export_package(principal, assessment_id))


@router.get("/package/verify", summary="Recompute every hash of the exported package")
def verify(assessment_id: AssessmentPath, principal: PrincipalDep, service: ServiceDep) -> Verification:
    return Verification(**service.verify_package(principal, assessment_id))


@router.get(
    "/package.zip",
    summary="Download the package as a zip",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}}},
)
def download(assessment_id: AssessmentPath, principal: PrincipalDep, service: ServiceDep) -> Response:
    return Response(
        service.package_zip(principal, assessment_id),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{assessment_id}.zip"'},
    )


@router.post("/package/tamper-demo", summary="DEMO: edit a copy of the package and show verification fails")
def tamper(
    assessment_id: AssessmentPath, principal: PrincipalDep, service: ServiceDep, settings: SettingsDep
) -> TamperDemo:
    if not settings.demo_endpoints:
        raise HTTPException(404, "demo endpoints are disabled (KCCS_DEMO_ENDPOINTS=false)")
    return TamperDemo(**service.tamper_demo(principal, assessment_id))
