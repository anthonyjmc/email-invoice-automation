from typing import Any

import httpx

from app.config import settings


async def sign_in_with_email_password(email: str, password: str) -> dict[str, Any] | None:
    """
    Email/password sign-in via Supabase Auth REST API (GoTrue).
    Returns token payload on success, or None on failure.
    """
    base = settings.SUPABASE_URL.rstrip("/")
    url = f"{base}/auth/v1/token"
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            params={"grant_type": "password"},
            headers=headers,
            json={"email": email.strip(), "password": password},
            timeout=20.0,
        )
    if response.status_code != 200:
        return None
    return response.json()


async def sign_out_with_access_token(access_token: str) -> None:
    """
    Revokes the refresh token server-side (invalidates refresh for this session).
    """
    base = settings.SUPABASE_URL.rstrip("/")
    url = f"{base}/auth/v1/logout"
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {access_token}",
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, timeout=15.0)
