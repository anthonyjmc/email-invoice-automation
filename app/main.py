import os
from contextlib import asynccontextmanager

import redis.asyncio as redis_async
from fastapi import FastAPI, Depends, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
from dotenv import load_dotenv
from app.csrf import get_or_create_csrf_token, verify_csrf_token
from app.security import verify_password
from app.config import settings
from app.db import get_supabase_for_api, get_supabase_for_request
from app.services.supabase_web_auth import sign_in_with_email_password, sign_out_with_access_token
from app.services.email_parser import (
    parse_mock_email,
    parse_eml_invoice,
    parse_msg_invoice,
    parse_pdf_invoice,
)
from app.services.invoice_service import save_invoice, list_invoices
from app.services.upload_security import (
    build_safe_temp_path,
    extension_from_upload_filename,
    read_upload_with_size_limit,
    reconcile_extension,
    run_optional_antivirus_scan,
    sniff_content_kind,
)
from app.rate_limit import check_rate_limited

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = None
    if settings.REDIS_URL:
        redis_client = redis_async.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        app.state.redis = redis_client
    else:
        app.state.redis = None
    yield
    if redis_client is not None:
        await redis_client.aclose()


templates = Jinja2Templates(directory="app/templates")
app = FastAPI(title="Email Invoice Automation Demo", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    max_age=settings.SESSION_MAX_AGE_SECONDS,
    same_site=settings.SESSION_COOKIE_SAMESITE,
    https_only=settings.SESSION_COOKIE_SECURE,
)

LOGIN_RATE_LIMIT_MAX_REQUESTS = 5
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 60
UPLOAD_RATE_LIMIT_MAX_REQUESTS = 10
UPLOAD_RATE_LIMIT_WINDOW_SECONDS = 300

LOGIN_ERROR_MESSAGES = {
    "invalid_credentials": "Invalid credentials. Please try again.",
    "rate_limited": "Too many login attempts. Please wait a minute and try again.",
    "csrf_invalid": "Security check failed. Please refresh the page and try again.",
}

DASHBOARD_ERROR_MESSAGES = {
    "auth_required": "Please log in to continue.",
    "unsupported": "Unsupported file type. Use .txt, .eml, .msg, or .pdf.",
    "no_file_name": "Invalid upload: file name is missing.",
    "unsafe_filename": "Invalid file name. Remove path characters and try again.",
    "file_too_large": "File is too large. Reduce size and try again.",
    "invalid_file_type": "File content does not match the declared type (or is not a supported invoice format).",
    "parse_failed": "Unable to process that file. Please verify format and content.",
    "save_failed": "Invoice was parsed but could not be saved. Please try again.",
    "rate_limited": "Too many uploads in a short period. Please wait and retry.",
    "csrf_invalid": "Security check failed. Please refresh the page and try again.",
    "av_misconfigured": "Antivirus scan is enabled but not configured. Set UPLOAD_AV_SCAN_COMMAND.",
    "av_unavailable": "Antivirus scanner is not available on the server.",
    "av_timeout": "Antivirus scan timed out. Try again later.",
    "av_rejected": "File failed antivirus scan and was not processed.",
}


def invoice_user_id_for_row(request: Request) -> str | None:
    """Attach Supabase auth user id to new invoice rows when using Supabase Auth."""
    if settings.WEB_AUTH_PROVIDER != "supabase":
        return None
    uid = request.session.get("auth_user_id")
    return str(uid) if uid else None


def require_auth(request: Request) -> bool:
    """
    Session-based auth: legacy shared password flag, or Supabase user id after Auth login.
    """
    if settings.WEB_AUTH_PROVIDER == "legacy":
        return bool(request.session.get("authenticated"))
    return bool(request.session.get("auth_user_id"))


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "rate_limit_backend": "redis" if settings.REDIS_URL else "memory",
    }


@app.post("/process-mock-email")
async def process_mock_email(_: None = Depends(verify_password)):
    """
    Process a local mock email file (examples/sample_invoice_email.txt),
    extract invoice fields, and save them to the database.
    This endpoint is protected by basic password verification.
    """
    path = Path("examples/sample_invoice_email.txt")
    data = parse_mock_email(str(path))

    # At this point, parse_mock_email already returns "invoice_date" as an ISO string
    # so we do NOT call .isoformat() here. If you ever change the parser to return
    # a datetime object, you can add a type check and convert accordingly.
    # Example:
    #   if isinstance(data.get("invoice_date"), (date, datetime)):
    #       data["invoice_date"] = data["invoice_date"].isoformat()

    db = get_supabase_for_api()
    save_invoice(data, client=db, user_id=None)
    return {"status": "saved", "invoice": data}


@app.get("/invoices")
async def get_invoices(_: None = Depends(verify_password)):
    """
    Return all invoices as JSON.
    This endpoint uses the same basic password verification as /process-mock-email.
    """
    db = get_supabase_for_api()
    return {"invoices": list_invoices(client=db)}


@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Render the login page.
    """
    error_code = request.query_params.get("error")
    error_message = LOGIN_ERROR_MESSAGES.get(error_code)
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "error_message": error_message,
            "csrf_token": csrf_token,
            "web_auth_provider": settings.WEB_AUTH_PROVIDER,
        },
    )


@app.post("/login")
async def login(
    request: Request,
    csrf_token: str | None = Form(None),
    password: str = Form(...),
    email: str | None = Form(None),
):
    """
    Login: legacy shared password, or Supabase Auth email/password (see WEB_AUTH_PROVIDER).
    CSRF token required on all POST logins.
    """
    if not verify_csrf_token(request, csrf_token):
        return RedirectResponse("/?error=csrf_invalid", status_code=302)

    if await check_rate_limited(
        request,
        action="login",
        max_requests=LOGIN_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    ):
        return RedirectResponse("/?error=rate_limited", status_code=302)

    if settings.WEB_AUTH_PROVIDER == "legacy":
        if password != settings.AUTH_PASSWORD:
            return RedirectResponse("/?error=invalid_credentials", status_code=302)
        request.session["authenticated"] = True
        request.session.pop("auth_user_id", None)
        request.session.pop("user_email", None)
        request.session.pop("supabase_access_token", None)
        request.session.pop("supabase_refresh_token", None)
        return RedirectResponse("/dashboard", status_code=302)

    if not email or not email.strip():
        return RedirectResponse("/?error=invalid_credentials", status_code=302)

    payload = await sign_in_with_email_password(email.strip(), password)
    if not payload or not payload.get("user"):
        return RedirectResponse("/?error=invalid_credentials", status_code=302)

    user = payload["user"]
    request.session.pop("authenticated", None)
    request.session["auth_user_id"] = user.get("id")
    request.session["user_email"] = user.get("email")
    request.session["supabase_access_token"] = payload.get("access_token")
    request.session["supabase_refresh_token"] = payload.get("refresh_token") or ""
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """
    Render the dashboard with all saved invoices.
    Requires the user to be authenticated via session.
    """
    if not require_auth(request):
        return RedirectResponse("/?error=auth_required", status_code=302)

    error_code = request.query_params.get("error")
    success_code = request.query_params.get("success")
    error_message = DASHBOARD_ERROR_MESSAGES.get(error_code)
    success_message = "Invoice processed successfully." if success_code == "uploaded" else None
    db = get_supabase_for_request(request)
    try:
        invoices = list_invoices(client=db)
    except Exception:
        invoices = []
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "invoices": invoices,
            "error_message": error_message,
            "success_message": success_message,
            "csrf_token": csrf_token,
            "web_auth_provider": settings.WEB_AUTH_PROVIDER,
        },
    )


@app.get("/process-ui")
async def process_ui(request: Request):
    """
    Process the sample mock email from the UI and redirect back to the dashboard.
    """
    if not require_auth(request):
        return RedirectResponse("/?error=auth_required", status_code=302)

    db = get_supabase_for_request(request)
    uid = invoice_user_id_for_row(request)
    try:
        data = parse_mock_email("examples/sample_invoice_email.txt")
    except Exception:
        return RedirectResponse("/dashboard?error=parse_failed", status_code=302)
    try:
        save_invoice(data, client=db, user_id=uid)
    except Exception:
        return RedirectResponse("/dashboard?error=save_failed", status_code=302)
    return RedirectResponse("/dashboard?success=uploaded", status_code=302)


@app.post("/upload-invoice")
async def upload_invoice(
    request: Request,
    csrf_token: str | None = Form(None),
    file: UploadFile = File(...),
):
    """
    Upload an invoice email file (.txt, .eml, .msg, .pdf),
    parse it using the appropriate parser, and save to the database.
    """
    if not require_auth(request):
        return RedirectResponse("/?error=auth_required", status_code=302)
    if not verify_csrf_token(request, csrf_token):
        return RedirectResponse("/dashboard?error=csrf_invalid", status_code=302)
    if await check_rate_limited(
        request,
        action="upload_invoice",
        max_requests=UPLOAD_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=UPLOAD_RATE_LIMIT_WINDOW_SECONDS,
    ):
        return RedirectResponse("/dashboard?error=rate_limited", status_code=302)
    declared_ext, name_error = extension_from_upload_filename(file.filename)
    if name_error:
        return RedirectResponse(f"/dashboard?error={name_error}", status_code=302)

    content, read_error = await read_upload_with_size_limit(file, settings.MAX_UPLOAD_FILE_BYTES)
    if read_error:
        return RedirectResponse(f"/dashboard?error={read_error}", status_code=302)

    sniffed = sniff_content_kind(content)
    canonical_ext, kind_error = reconcile_extension(declared_ext=declared_ext, sniffed=sniffed)
    if kind_error:
        return RedirectResponse(f"/dashboard?error={kind_error}", status_code=302)

    file_path = build_safe_temp_path(canonical_ext)
    try:
        with open(file_path, "wb") as f:
            f.write(content)

        av_error = run_optional_antivirus_scan(
            file_path=file_path,
            file_extension=canonical_ext,
            enabled=settings.UPLOAD_AV_SCAN_ENABLED,
            pdf_only=settings.UPLOAD_AV_SCAN_PDF_ONLY,
            command_template=settings.UPLOAD_AV_SCAN_COMMAND,
            timeout_seconds=settings.UPLOAD_AV_SCAN_TIMEOUT_SECONDS,
        )
        if av_error:
            return RedirectResponse(f"/dashboard?error={av_error}", status_code=302)

        try:
            if canonical_ext == "txt":
                data = parse_mock_email(file_path)
            elif canonical_ext == "eml":
                data = parse_eml_invoice(file_path)
            elif canonical_ext == "msg":
                data = parse_msg_invoice(file_path)
            elif canonical_ext == "pdf":
                data = parse_pdf_invoice(file_path)
            else:
                return RedirectResponse("/dashboard?error=unsupported", status_code=302)
        except Exception:
            return RedirectResponse("/dashboard?error=parse_failed", status_code=302)

        db = get_supabase_for_request(request)
        uid = invoice_user_id_for_row(request)
        try:
            save_invoice(data, client=db, user_id=uid)
        except Exception:
            return RedirectResponse("/dashboard?error=save_failed", status_code=302)
        return RedirectResponse("/dashboard?success=uploaded", status_code=302)
    finally:
        try:
            os.unlink(file_path)
        except OSError:
            pass


@app.get("/logout")
async def logout(request: Request):
    """
    Clear the session and redirect back to the login page.
    """
    if settings.WEB_AUTH_PROVIDER == "supabase":
        access_token = request.session.get("supabase_access_token")
        if isinstance(access_token, str) and access_token:
            try:
                await sign_out_with_access_token(access_token)
            except Exception:
                pass
    request.session.clear()
    return RedirectResponse("/", status_code=302)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

