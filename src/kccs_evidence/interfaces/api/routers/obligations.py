"""Regulatory notification obligations: the deadline queue and the state machine."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from ....application.access import Principal
from ....domain.temporal import iso
from ..deps import EventPath, PrincipalDep, ServiceDep, TenantPath, require_role
from ..schemas import ObligationOut, ObligationQueue, Problem, TransitionRequest, TransitionResult

router = APIRouter(
    prefix="/api/v1",
    tags=["notification obligations"],
    responses={
        401: {"model": Problem},
        403: {"model": Problem},
        404: {"model": Problem},
        409: {"model": Problem},
        422: {"model": Problem},
    },
)
RaDep = Annotated[Principal, Depends(require_role("REGULATORY_AFFAIRS"))]


def _queue(
    service: ServiceDep,
    principal: Principal,
    tenant: str | None,
    as_of: datetime | None,
    margin_hours: float,
    only_at_risk: bool,
    received_within_hours: float | None,
) -> ObligationQueue:
    if as_of is not None and as_of.tzinfo is None:
        raise HTTPException(422, "as_of must carry a timezone, e.g. 2026-07-29T12:00:00Z")
    now = as_of or service.clock()
    items = service.obligations(
        principal,
        tenant=tenant,
        now=now,
        margin_hours=margin_hours,
        only_at_risk=only_at_risk,
        received_within_hours=received_within_hours,
    )
    return ObligationQueue(
        as_of_utc=iso(now),
        margin_hours=margin_hours,
        only_at_risk=only_at_risk,
        count=len(items),
        items=[ObligationOut(**o) for o in items],
    )


AsOf = Annotated[datetime | None, Query(description="Evaluate the queue as of this instant (default: now)")]
Margin = Annotated[float, Query(ge=0, le=720, description="At-risk window in hours")]
Received = Annotated[float | None, Query(ge=0, le=24 * 400, description="Only alerts received in the last N hours")]


@router.get("/obligations/queue", summary="Earliest-deadline-first queue across every tenant in the caller's scope")
def queue(
    principal: PrincipalDep,
    service: ServiceDep,
    as_of: AsOf = None,
    margin_hours: Margin = 24,
    only_at_risk: bool = True,
    received_within_hours: Received = None,
) -> ObligationQueue:
    return _queue(service, principal, None, as_of, margin_hours, only_at_risk, received_within_hours)


@router.get("/tenants/{tenant}/obligations", summary="One tenant's obligations, deadline first")
def tenant_obligations(
    tenant: TenantPath,
    principal: PrincipalDep,
    service: ServiceDep,
    as_of: AsOf = None,
    margin_hours: Margin = 24,
    only_at_risk: bool = False,
    received_within_hours: Received = None,
) -> ObligationQueue:
    return _queue(service, principal, tenant, as_of, margin_hours, only_at_risk, received_within_hours)


@router.post(
    "/tenants/{tenant}/obligations/{event_id}/transitions",
    summary="Move an obligation through its state machine (optimistic lock + Idempotency-Key)",
)
def transition(
    tenant: TenantPath,
    event_id: EventPath,
    body: TransitionRequest,
    principal: RaDep,
    service: ServiceDep,
    response: Response,
    idempotency_key: Annotated[str | None, Header(max_length=100)] = None,
) -> TransitionResult:
    ob, applied = service.transition_obligation(
        principal,
        tenant,
        event_id,
        to_state=body.to_state,
        expected_version=body.expected_version,
        note=body.note,
        idempotency_key=idempotency_key,
    )
    if not applied:
        response.headers["Idempotent-Replay"] = "true"
    return TransitionResult(applied=applied, obligation=ObligationOut(**ob))
