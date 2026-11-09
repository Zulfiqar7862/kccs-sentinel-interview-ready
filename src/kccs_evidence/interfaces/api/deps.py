"""FastAPI dependencies: the service singleton, the caller's principal and role checks.

Prototype authentication: the caller declares itself with headers. In production
these values come from a verified OIDC token (actor = subject, tenants and roles =
claims) issued by the regional cell's identity provider; the rest of the code
does not change because it only ever sees a `Principal`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Path, Request

from ...application.access import Principal
from ...application.service import KernelService
from .settings import Settings

TENANT_RE = r"^T-[A-Z]{2,20}$"
EVENT_RE = r"^EXC-\d{3,10}$"
ASSESSMENT_RE = r"^ASM-[0-9a-f]{24}$"
_ACTOR_RE = re.compile(r"^[A-Za-z0-9._@-]{1,64}$")
ROLES = {"QA_REVIEWER", "QA_DATA_STEWARD", "REGULATORY_AFFAIRS", "PLATFORM_ADMIN"}


def get_service(request: Request) -> KernelService:
    service: KernelService = request.app.state.service
    return service


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_principal(
    request: Request,
    x_actor: Annotated[
        str | None, Header(description="Who is calling (prototype stand-in for the token subject)")
    ] = None,
    x_tenant_scope: Annotated[str | None, Header(description="Comma list of tenants the caller may access")] = None,
    x_roles: Annotated[str | None, Header(description="Comma list of roles; default QA_REVIEWER")] = None,
) -> Principal:
    if not x_actor or not x_tenant_scope:
        raise HTTPException(401, "X-Actor and X-Tenant-Scope headers are required")
    if not _ACTOR_RE.match(x_actor):
        raise HTTPException(422, "X-Actor has invalid characters")
    tenants = frozenset(t.strip() for t in x_tenant_scope.split(",") if t.strip())
    if not tenants or any(not re.match(TENANT_RE, t) for t in tenants):
        raise HTTPException(422, "X-Tenant-Scope must be a comma list of tenant codes like T-KAVERI")
    roles = frozenset(r.strip() for r in (x_roles or "QA_REVIEWER").split(",") if r.strip())
    unknown = roles - ROLES
    if unknown:
        raise HTTPException(422, f"unknown roles {sorted(unknown)}; allowed {sorted(ROLES)}")
    request.state.actor = x_actor
    return Principal(x_actor, tenants, roles)


def require_role(role: str) -> Callable[[Principal], Principal]:
    def check(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if role not in principal.roles:
            raise HTTPException(403, f"role {role} required")
        return principal

    return check


ServiceDep = Annotated[KernelService, Depends(get_service)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
TenantPath = Annotated[str, Path(pattern=TENANT_RE, description="Tenant code, e.g. T-KAVERI")]
EventPath = Annotated[str, Path(pattern=EVENT_RE, description="Event id, e.g. EXC-107133")]
AssessmentPath = Annotated[str, Path(pattern=ASSESSMENT_RE, description="Content-addressed assessment id")]
