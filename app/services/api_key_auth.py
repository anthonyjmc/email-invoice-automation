"""
Machine API authentication: Bearer / X-API-Key with DB-backed keys + scopes,
optional legacy X-App-Password, and audit rows (service_role required for keys).
"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timezone
import structlog
from fastapi import Header, HTTPException, Request, status
from supabase import Client

from app.config import settings
from app.db import create_service_role_client

logger = structlog.get_logger(__name__)

_key_cache: tuple[float, list[dict]] = (0.0, [])


def hash_api_secret(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _fetch_active_keys(client: Client) -> list[dict]:
    res = (
        client.table("machine_api_keys")
        .select("id,name,key_hash,scopes")
        .is_("revoked_at", "null")
        .execute()
    )
    return res.data or []


def get_active_api_keys_cached() -> list[dict]:
    global _key_cache
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        return []
    now = time.monotonic()
    ttl = settings.API_KEY_CACHE_SECONDS
    if ttl > 0 and now - _key_cache[0] < ttl and _key_cache[1]:
        return _key_cache[1]
    try:
        client = create_service_role_client()
        rows = _fetch_active_keys(client)
    except Exception as exc:
        logger.warning("machine_api_keys_load_failed", error=str(exc))
        rows = []
    _key_cache = (now, rows)
    return rows


def verify_api_key_plain(plaintext: str) -> dict | None:
    if not plaintext:
        return None
    digest = hash_api_secret(plaintext)
    for row in get_active_api_keys_cached():
        stored = row.get("key_hash")
        if isinstance(stored, str) and hmac.compare_digest(stored, digest):
            return row
    return None


def invalidate_api_key_cache() -> None:
    global _key_cache
    _key_cache = (0.0, [])


def _scopes_sufficient(granted: list[str], required: tuple[str, ...]) -> bool:
    g = set(granted or [])
    if "invoices:admin" in g:
        return True
    return all(s in g for s in required)


def audit_machine_request(
    *,
    service: Client,
    api_key_id: str | None,
    legacy_auth: bool,
    request: Request,
    status_code: int,
) -> None:
    try:
        ip = request.client.host if request.client else ""
        service.table("machine_api_audit").insert(
            {
                "api_key_id": api_key_id,
                "legacy_auth": legacy_auth,
                "route": request.url.path,
                "method": request.method,
                "client_ip": ip or None,
                "status_code": status_code,
            }
        ).execute()
    except Exception as exc:
        logger.warning("machine_api_audit_insert_failed", error=str(exc))


def touch_api_key_used(service: Client, api_key_id: str) -> None:
    try:
        ts = datetime.now(timezone.utc).isoformat()
        service.table("machine_api_keys").update({"last_used_at": ts}).eq("id", api_key_id).execute()
    except Exception as exc:
        logger.warning("machine_api_key_touch_failed", api_key_id=api_key_id, error=str(exc))


def require_machine_scopes(*required_scopes: str):
    """
    FastAPI dependency: Bearer <secret> or X-API-Key, or legacy X-App-Password (if enabled).
    Scopes: invoices:read, invoices:write, invoices:admin (implies all).
    """

    async def _dependency(
        request: Request,
        authorization: str | None = Header(None),
        x_api_key: str | None = Header(None, alias="X-API-Key"),
        x_app_password: str | None = Header(None, alias="X-App-Password"),
    ) -> None:
        token: str | None = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip() or None
        if not token and x_api_key:
            token = x_api_key.strip() or None

        matched: dict | None = None
        legacy = False

        if settings.API_LEGACY_HEADER_AUTH_ENABLED and x_app_password == settings.APP_PASSWORD:
            matched = {
                "id": None,
                "scopes": ["invoices:read", "invoices:write"],
                "name": "legacy-x-app-password",
            }
            legacy = True
        elif token:
            ap = settings.APP_PASSWORD
            if settings.API_LEGACY_HEADER_AUTH_ENABLED and (
                (len(token) == len(ap) and hmac.compare_digest(token, ap)) or token == ap
            ):
                matched = {
                    "id": None,
                    "scopes": ["invoices:read", "invoices:write"],
                    "name": "legacy-bearer-app-password",
                }
                legacy = True
            else:
                matched = verify_api_key_plain(token)

        if not matched:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API credentials",
            )

        scopes = list(matched.get("scopes") or [])
        if not _scopes_sufficient(scopes, required_scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient API key scope",
            )

        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            return

        try:
            service = create_service_role_client()
        except Exception:
            return

        kid = matched.get("id")
        kid_str = str(kid) if kid else None
        audit_machine_request(
            service=service,
            api_key_id=kid_str,
            legacy_auth=legacy,
            request=request,
            status_code=200,
        )
        if kid_str and not legacy:
            touch_api_key_used(service, kid_str)

    return _dependency
