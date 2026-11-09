"""Tenant-scoped events and their assessments."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from ..deps import EventPath, PrincipalDep, ServiceDep, TenantPath
from ..schemas import AssessmentEnvelope, AssessmentHistoryItem, AssessRequest, EventDetail, EventList, Problem

router = APIRouter(
    prefix="/api/v1/tenants/{tenant}",
    tags=["events & assessments"],
    responses={
        401: {"model": Problem},
        403: {"model": Problem},
        404: {"model": Problem},
        422: {"model": Problem},
        503: {"model": Problem},
    },
)


@router.get("/events", summary="List this tenant's alerts (input fields only, never outcomes)")
def list_events(
    tenant: TenantPath,
    principal: PrincipalDep,
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=80, description="Substring filter")] = None,
) -> EventList:
    page = service.list_events(principal, tenant, limit=limit, offset=offset, query=q)
    return EventList(tenant=tenant, total=page.total, limit=limit, offset=offset, items=page.items)


@router.get("/events/{event_id}", summary="One alert as received")
def get_event(tenant: TenantPath, event_id: EventPath, principal: PrincipalDep, service: ServiceDep) -> EventDetail:
    return EventDetail(**service.get_event(principal, tenant, event_id))


@router.post(
    "/events/{event_id}/assessments",
    status_code=201,
    summary="Build and store an assessment (idempotent: same inputs give the same id, 200 if it exists)",
)
def assess(
    tenant: TenantPath,
    event_id: EventPath,
    body: AssessRequest,
    principal: PrincipalDep,
    service: ServiceDep,
    response: Response,
) -> AssessmentEnvelope:
    payload, inserted = service.assess(
        principal, tenant, event_id, knowledge_cutoff=body.knowledge_cutoff, mode=body.mode
    )
    if not inserted:
        response.status_code = 200
    response.headers["Location"] = f"/api/v1/assessments/{payload['assessment_id']}"
    return AssessmentEnvelope(
        stored="new" if inserted else "existing",
        assessment_id=payload["assessment_id"],
        status=payload["disposition_evidence_status"],
        assessment=payload,
    )


@router.get("/events/{event_id}/assessments", summary="Every stored assessment of this event, oldest first")
def history(
    tenant: TenantPath, event_id: EventPath, principal: PrincipalDep, service: ServiceDep
) -> list[AssessmentHistoryItem]:
    return [AssessmentHistoryItem(**h) for h in service.assessment_history(principal, tenant, event_id)]
