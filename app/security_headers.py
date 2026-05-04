"""
Security headers (HSTS, CSP, X-Content-Type-Options, etc.) for production hardening.
TLS termination remains at the reverse proxy; HSTS is only sent when explicitly enabled (HTTPS).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

DEFAULT_CSP = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if not settings.SECURITY_HEADERS_ENABLED:
            return response

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = settings.SECURITY_X_FRAME_OPTIONS
        response.headers["Referrer-Policy"] = settings.SECURITY_REFERRER_POLICY
        response.headers["Permissions-Policy"] = settings.SECURITY_PERMISSIONS_POLICY

        csp = settings.SECURITY_CSP or DEFAULT_CSP
        if settings.SECURITY_CSP_UPGRADE_INSECURE and "upgrade-insecure-requests" not in csp:
            csp = f"{csp}; upgrade-insecure-requests"
        response.headers["Content-Security-Policy"] = csp

        if settings.SECURITY_ENABLE_HSTS:
            hsts = f"max-age={settings.SECURITY_HSTS_MAX_AGE}"
            if settings.SECURITY_HSTS_INCLUDE_SUBDOMAINS:
                hsts = f"{hsts}; includeSubDomains"
            if settings.SECURITY_HSTS_PRELOAD:
                hsts = f"{hsts}; preload"
            response.headers["Strict-Transport-Security"] = hsts

        if settings.SECURITY_CROSS_ORIGIN_OPENER_POLICY:
            response.headers["Cross-Origin-Opener-Policy"] = settings.SECURITY_CROSS_ORIGIN_OPENER_POLICY

        return response
