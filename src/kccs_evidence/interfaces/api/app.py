"""FastAPI application factory (composition root for the HTTP interface).

Wires settings -> SQLite store -> KernelService, installs structured request
logging, problem-details errors, the routers and the static web UI.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import Counter
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from importlib import resources
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from ... import __version__
from ...application.service import KernelService
from ...domain.temporal import UTC
from ...infrastructure.sqlite_store import Store
from ...infrastructure.workbook import load_workbook_snapshot
from .errors import install_error_handlers
from .logging_config import configure_logging
from .routers import assessments, audit, events, obligations, system
from .settings import Settings

log = logging.getLogger("kccs.api")

DESCRIPTION = """
Tenant-scoped, bitemporal **evidence kernel** for temperature-excursion alerts.

It assembles the evidence a QA reviewer needs (product identity, SOP revision in force, admissible
stability study, notification deadline), records exactly what it used, and **abstains instead of guessing**.
It never issues a disposition: a named human signs.

Prototype authentication: send `X-Actor`, `X-Tenant-Scope` (comma list) and optionally `X-Roles`
(`QA_REVIEWER`, `QA_DATA_STEWARD`, `REGULATORY_AFFAIRS`, `PLATFORM_ADMIN`). Errors use RFC 9457 problem details.
"""


def _clock(settings: Settings) -> Callable[[], datetime]:
    fixed = settings.fixed_now
    if fixed is not None:
        return lambda: fixed
    return lambda: datetime.now(UTC)


def build_service(settings: Settings) -> KernelService:
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    service = KernelService(Store(settings.db_path), settings.artifacts_dir, _clock(settings))
    if settings.autoload and settings.workbook.exists():
        stats = service.ingest(load_workbook_snapshot(settings.workbook))
        log.info("workbook autoloaded", extra={"event": "AUTOLOAD", "detail": stats})
    elif settings.autoload:
        log.warning(
            "workbook not found; API starts not-ready",
            extra={"event": "AUTOLOAD_SKIPPED", "detail": str(settings.workbook)},
        )
    return service


def create_app(settings: Settings | None = None, service: KernelService | None = None) -> FastAPI:
    """Build the app. Tests may inject a ready `service`; otherwise it is built from settings at startup."""
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.service = service or build_service(settings)
        log.info(
            "api started", extra={"event": "STARTUP", "detail": {"version": __version__, "db": str(settings.db_path)}}
        )
        yield
        log.info("api stopped", extra={"event": "SHUTDOWN"})

    app = FastAPI(
        title="KCCS Sentinel Evidence Kernel", version=__version__, description=DESCRIPTION, lifespan=lifespan
    )
    app.state.settings = settings
    app.state.request_counter = Counter()

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = rid
        route = request.scope.get("route")
        template = getattr(route, "path", "unmatched")
        app.state.request_counter[(template, response.status_code)] += 1
        log.info(
            "request",
            extra={
                "request_id": rid,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": elapsed,
                "actor": getattr(request.state, "actor", None),
            },
        )
        return response

    install_error_handlers(app)
    for module in (system, events, assessments, obligations, audit):
        app.include_router(module.router)
    app.include_router(audit.tenants_router)

    web_dir = Path(str(resources.files("kccs_evidence.interfaces").joinpath("web")))
    app.mount("/ui", StaticFiles(directory=web_dir, html=True), name="ui")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/ui/")

    return app
