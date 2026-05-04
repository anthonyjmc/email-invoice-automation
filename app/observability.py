"""
Correlation IDs (X-Request-ID), request-scoped structlog context, access logs, Prometheus hooks.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings
from app.metrics import record_http_request

logger = structlog.get_logger(__name__)


def route_label(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        path = getattr(route, "path", None)
        if isinstance(path, str) and path:
            return path
    p = request.url.path
    return p if len(p) <= 128 else p[:128]


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Assigns correlation_id (from X-Request-ID / X-Correlation-ID or new UUID),
    binds structlog contextvars, logs access, records Prometheus metrics.
    """

    async def dispatch(self, request: Request, call_next):
        header_cid = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")
        correlation_id = header_cid.strip() if header_cid and header_cid.strip() else str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = correlation_id
        except Exception:
            duration_s = time.perf_counter() - start
            if settings.OBSERVABILITY_METRICS_ENABLED:
                record_http_request(
                    method=request.method,
                    route=route_label(request),
                    status_code=500,
                    duration_s=duration_s,
                )
            logger.exception(
                "http_request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_s * 1000, 2),
            )
            structlog.contextvars.clear_contextvars()
            raise

        duration_s = time.perf_counter() - start
        if settings.OBSERVABILITY_METRICS_ENABLED:
            record_http_request(
                method=request.method,
                route=route_label(request),
                status_code=status_code,
                duration_s=duration_s,
            )
        if settings.OBSERVABILITY_ACCESS_LOG:
            fields = {
                "method": request.method,
                "path": request.url.path,
                "route": route_label(request),
                "status_code": status_code,
                "duration_ms": round(duration_s * 1000, 2),
            }
            if status_code >= 500:
                logger.warning("http_request", **fields)
            else:
                logger.info("http_request", **fields)
        structlog.contextvars.clear_contextvars()
        return response
