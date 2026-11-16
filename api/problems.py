"""Consistent error envelope: RFC 9457 problem details (`application/problem+json`) for every error.

Every response body has `type`, `title`, `status`, `detail`, `instance`, a stable machine-readable
`code`, and the `request_id` that also appears in the logs and the `X-Request-ID` response header."""

from __future__ import annotations

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from agents.orchestrator import InvalidTransition, ValidationFailed
from agents.providers.consent import ConsentError
from api.request_context import request_id

log = logging.getLogger("udyampulse.api")
PROBLEM_BASE = "https://udyampulse.example/problems/"
MEDIA_TYPE = "application/problem+json"

_DEFAULT_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed",
                  409: "conflict", 422: "validation_failed", 429: "rate_limited", 500: "internal_error",
                  503: "service_unavailable"}


def problem(request: Request, status: int, detail: str, *, code: str | None = None, title: str | None = None,
            headers: dict[str, str] | None = None, **extra: object) -> JSONResponse:
    code = code or _DEFAULT_CODES.get(status, "error")
    rid = getattr(request.state, "request_id", None) or request_id()
    body = {
        "type": PROBLEM_BASE + code,
        "title": title or HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "request_id": rid,
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type=MEDIA_TYPE, headers={**(headers or {}), "X-Request-ID": rid})


def install(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        return problem(request, exc.status_code, detail, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def request_invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()]
        detail = "; ".join(f"{e['field']}: {e['message']}" if e["field"] else e["message"] for e in errors)
        return problem(request, 422, detail or "The request is not valid", errors=errors)

    @app.exception_handler(ConsentError)
    async def consent_required(request: Request, exc: ConsentError) -> JSONResponse:
        return problem(request, 403, str(exc), code="consent_required", title="Consent required")

    @app.exception_handler(InvalidTransition)
    async def invalid_state(request: Request, exc: InvalidTransition) -> JSONResponse:
        return problem(request, 409, str(exc), code="invalid_state", title="Invalid state for this action")

    @app.exception_handler(ValidationFailed)
    async def validation_failed(request: Request, exc: ValidationFailed) -> JSONResponse:
        return problem(request, 422, str(exc))

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        # The cause is logged with the request id; the client gets no internals.
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return problem(request, 500, "Something went wrong on our side. Quote the request id when reporting this.")
