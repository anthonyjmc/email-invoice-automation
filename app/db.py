from __future__ import annotations

from starlette.requests import Request
from supabase import Client, create_client

from app.config import settings


def create_anon_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


def create_service_role_client() -> Client:
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    if not key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not set. "
            "With RLS enabled, legacy/API routes need the service role on the server only (never expose it to the browser)."
        )
    return create_client(settings.SUPABASE_URL, key)


def create_user_scoped_client(access_token: str, refresh_token: str) -> Client:
    """
    PostgREST requests use the end-user JWT so RLS policies (auth.uid()) apply.
    If refresh_token is empty, the access token is passed as a fallback (some flows only return access).
    """
    client = create_anon_client()
    refresh = refresh_token if refresh_token else access_token
    client.auth.set_session(access_token, refresh)
    return client


def get_supabase_for_request(request: Request) -> Client:
    """
    Dashboard / upload: Supabase Auth session uses anon key + user JWT.
    Legacy mode uses service role when configured (server-side only), else anon.
    """
    if settings.WEB_AUTH_PROVIDER == "supabase":
        access = request.session.get("supabase_access_token")
        refresh = request.session.get("supabase_refresh_token")
        if not isinstance(access, str) or not access:
            return create_anon_client()
        refresh_str = refresh if isinstance(refresh, str) else ""
        return create_user_scoped_client(access, refresh_str)
    if settings.SUPABASE_SERVICE_ROLE_KEY:
        return create_service_role_client()
    return create_anon_client()


def get_supabase_for_api() -> Client:
    """
    Machine routes (X-App-Password): prefer service role so inserts/selects work with RLS
    without a user JWT. Falls back to anon if service role is not configured (pre-RLS demos).
    """
    if settings.SUPABASE_SERVICE_ROLE_KEY:
        return create_service_role_client()
    return create_anon_client()


supabase = create_anon_client()
