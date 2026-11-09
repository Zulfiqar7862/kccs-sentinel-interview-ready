"""One error shape for every failure: RFC 9457 problem details (application/problem+json)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ...application.access import TenantAccessDenied
from ...application.service import NotReady
from ...domain.obligations import IllegalTransition, PolicyIncomplete

log = logging.getLogger("kccs.api")
PROBLEM = "application/problem+json"


def problem(request: Request, status: int, title: str, detail: str, errors: list | None = None) -> JSONResponse:
    body = {
        "type": f"https://kccs.example/problems/{title.lower().replace(' ', '-')}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "request_id": getattr(request.state, "request_id", None),
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(TenantAccessDenied)
    async def _denied(request: Request, exc: TenantAccessDenied) -> JSONResponse:
        return problem(request, 403, "Access denied", str(exc))

    @app.exception_handler(KeyError)
    async def _not_found(request: Request, exc: KeyError) -> JSONResponse:
        return problem(request, 404, "Not found", str(exc.args[0] if exc.args else exc))

    @app.exception_handler(IllegalTransition)
    async def _conflict(request: Request, exc: IllegalTransition) -> JSONResponse:
        return problem(request, 409, "Conflict", str(exc))

    @app.exception_handler(NotReady)
    async def _not_ready(request: Request, exc: NotReady) -> JSONResponse:
        return problem(request, 503, "Not ready", str(exc))

    @app.exception_handler(PolicyIncomplete)
    async def _policy(request: Request, exc: PolicyIncomplete) -> JSONResponse:
        return problem(request, 422, "Policy incomplete", str(exc))

    @app.exception_handler(ValueError)
    async def _invalid(request: Request, exc: ValueError) -> JSONResponse:
        return problem(request, 422, "Invalid input", str(exc))

    @app.exception_handler(FileNotFoundError)
    async def _missing_file(request: Request, exc: FileNotFoundError) -> JSONResponse:
        return problem(request, 404, "File not found", str(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errs = [{"loc": list(e.get("loc", ())), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return problem(request, 422, "Validation failed", "request did not match the schema", errs)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(
            request, exc.status_code, str(exc.detail) if exc.status_code != 404 else "Not found", str(exc.detail)
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
        return problem(request, 500, "Internal error", "unexpected error; see server log with this request_id")
