"""
Global error handling: generic client responses, full detail only in structured logs.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.config import settings

logger = structlog.get_logger(__name__)

GENERIC_SERVER_MESSAGE = "Something went wrong on our side. Please try again later."
GENERIC_SERVER_JSON = {"error": GENERIC_SERVER_MESSAGE}

_HTML_500 = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>Error</title></head>
<body>
<p>An unexpected error occurred. Please try again later.</p>
</body>
</html>"""


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


def _json_safe_payload(base: dict, request: Request) -> dict:
    rid = _request_id(request)
    if rid:
        return {**base, "request_id": rid}
    return dict(base)


def _prefers_html(request: Request) -> bool:
    accept = request.headers.get("accept") or ""
    if "text/html" in accept:
        return True
    if accept.strip().startswith("application/json"):
        return False
    return False


def _api_path(path: str) -> bool:
    return path in ("/invoices", "/process-mock-email")


def _redirect_for_unhandled(request: Request) -> RedirectResponse | None:
    method = request.method
    path = request.url.path
    if method == "POST" and path == "/login":
        return RedirectResponse("/?error=server_error", status_code=302)
    if method == "POST" and path == "/upload-invoice":
        return RedirectResponse("/dashboard?error=server_error", status_code=302)
    if method == "GET" and path == "/process-ui":
        return RedirectResponse("/dashboard?error=server_error", status_code=302)
    if _prefers_html(request):
        if path == "/":
            return RedirectResponse("/?error=server_error", status_code=302)
        if path == "/dashboard":
            return RedirectResponse("/dashboard?error=server_error", status_code=302)
    return None


def _generic_500_response(request: Request) -> JSONResponse | HTMLResponse | RedirectResponse:
    if _api_path(request.url.path):
        return JSONResponse(_json_safe_payload(GENERIC_SERVER_JSON, request), status_code=500)
    redirect = _redirect_for_unhandled(request)
    if redirect is not None:
        return redirect
    if _prefers_html(request):
        return HTMLResponse(content=_HTML_500, status_code=500)
    return JSONResponse(_json_safe_payload(GENERIC_SERVER_JSON, request), status_code=500)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = _request_id(request)
        logger.warning(
            "request_validation_failed",
            path=request.url.path,
            errors=exc.errors(),
            request_id=rid,
        )
        if settings.APP_DEBUG:
            return JSONResponse({"detail": exc.errors()}, status_code=422)
        return JSONResponse(
            _json_safe_payload({"error": "Invalid request."}, request),
            status_code=422,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse | HTMLResponse:
        rid = _request_id(request)
        if exc.status_code >= 500:
            logger.error(
                "http_exception",
                status_code=exc.status_code,
                detail=exc.detail,
                path=request.url.path,
                request_id=rid,
            )
            if _api_path(request.url.path):
                return JSONResponse(_json_safe_payload(GENERIC_SERVER_JSON, request), status_code=exc.status_code)
            if _prefers_html(request):
                return HTMLResponse(content=_HTML_500, status_code=exc.status_code)
            return JSONResponse(_json_safe_payload(GENERIC_SERVER_JSON, request), status_code=exc.status_code)

        detail = exc.detail
        if isinstance(detail, str):
            return JSONResponse({"detail": detail}, status_code=exc.status_code)
        return JSONResponse({"detail": detail}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse | HTMLResponse | RedirectResponse:
        rid = _request_id(request)
        logger.exception(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            exc_type=type(exc).__name__,
            request_id=rid,
        )
        return _generic_500_response(request)
