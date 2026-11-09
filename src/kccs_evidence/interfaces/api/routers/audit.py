"""Source corrections (append-only) and the tenant audit trail."""

from __future__ import annotations

from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ....application.access import Principal
from ..deps import PrincipalDep, ServiceDep, TenantPath, require_role
from ..schemas import AuditEvent, CorrectionRequest, CorrectionResult, Problem

router = APIRouter(
    prefix="/api/v1/tenants/{tenant}",
    tags=["corrections & audit"],
    responses={401: {"model": Problem}, 403: {"model": Problem}, 404: {"model": Problem}, 422: {"model": Problem}},
)
StewardDep = Annotated[Principal, Depends(require_role("QA_DATA_STEWARD"))]


@router.post(
    "/corrections", status_code=201, summary="Append a corrected version of a source record (never overwrites)"
)
def correct(
    tenant: TenantPath, body: CorrectionRequest, principal: StewardDep, service: ServiceDep
) -> CorrectionResult:
    return CorrectionResult(
        **service.correct(
            principal,
            tenant,
            sheet=body.sheet,
            record_key=body.record_key,
            changes=dict(body.set),
            reason=body.reason,
            recorded_at=body.recorded_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    )


@router.get("/audit", summary="Append-only audit trail for this tenant, including denied attempts")
def audit(
    tenant: TenantPath, principal: PrincipalDep, service: ServiceDep, limit: Annotated[int, Query(ge=1, le=1000)] = 200
) -> list[AuditEvent]:
    return [AuditEvent(**a) for a in service.audit_trail(principal, tenant, limit=limit)]


tenants_router = APIRouter(prefix="/api/v1", tags=["corrections & audit"])


@tenants_router.get("/tenants", summary="Tenants in the caller's scope that have data")
def tenants(principal: PrincipalDep, service: ServiceDep) -> list[str]:
    return service.list_tenants(principal)
