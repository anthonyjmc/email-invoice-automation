import secrets

from starlette.requests import Request


def get_or_create_csrf_token(request: Request) -> str:
    existing = request.session.get("_csrf_token")
    if isinstance(existing, str) and len(existing) >= 32:
        return existing
    token = secrets.token_urlsafe(32)
    request.session["_csrf_token"] = token
    return token


def verify_csrf_token(request: Request, submitted: str | None) -> bool:
    if not submitted:
        return False
    expected = request.session.get("_csrf_token")
    if not isinstance(expected, str):
        return False
    return secrets.compare_digest(submitted, expected)
