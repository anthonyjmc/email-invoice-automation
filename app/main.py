import tempfile
import os
import time
from collections import deque
from threading import Lock
from fastapi import FastAPI, Depends, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
from dotenv import load_dotenv
from app.security import verify_password
from app.config import settings
from app.services.email_parser import (
    parse_mock_email,
    parse_eml_invoice,
    parse_msg_invoice,
    parse_pdf_invoice,
)
from app.services.invoice_service import save_invoice, list_invoices

load_dotenv()

templates = Jinja2Templates(directory="app/templates")
app = FastAPI(title="Email Invoice Automation Demo")

app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET)

RATE_LIMIT_STATE: dict[str, deque[float]] = {}
RATE_LIMIT_LOCK = Lock()

LOGIN_RATE_LIMIT_MAX_REQUESTS = 5
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 60
UPLOAD_RATE_LIMIT_MAX_REQUESTS = 10
UPLOAD_RATE_LIMIT_WINDOW_SECONDS = 300

LOGIN_ERROR_MESSAGES = {
    "invalid_credentials": "Invalid password. Please try again.",
    "rate_limited": "Too many login attempts. Please wait a minute and try again.",
}

DASHBOARD_ERROR_MESSAGES = {
    "auth_required": "Please log in to continue.",
    "unsupported": "Unsupported file type. Use .txt, .eml, .msg, or .pdf.",
    "no_file_name": "Invalid upload: file name is missing.",
    "parse_failed": "Unable to process that file. Please verify format and content.",
    "save_failed": "Invoice was parsed but could not be saved. Please try again.",
    "list_failed": "Could not load invoices right now. Please refresh and try again.",
    "rate_limited": "Too many uploads in a short period. Please wait and retry.",
}


def get_client_ip(request: Request) -> str:
    client = request.client
    if not client:
        return "unknown"
    return client.host or "unknown"


def is_rate_limited(*, request: Request, action: str, max_requests: int, window_seconds: int) -> bool:
    now = time.monotonic()
    client_ip = get_client_ip(request)
    state_key = f"{action}:{client_ip}"
    with RATE_LIMIT_LOCK:
        request_times = RATE_LIMIT_STATE.get(state_key)
        if request_times is None:
            request_times = deque()
            RATE_LIMIT_STATE[state_key] = request_times
        while request_times and now - request_times[0] > window_seconds:
            request_times.popleft()
        if len(request_times) >= max_requests:
            return True
        request_times.append(now)
    return False


def require_auth(request: Request) -> bool:
    """
    Simple session-based auth check.
    Returns True if the user is authenticated, otherwise False.
    """
    return bool(request.session.get("authenticated"))


@app.get("/health")
async def health():
    return {"status": "ok"}


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

    save_invoice(data)
    return {"status": "saved", "invoice": data}


@app.get("/invoices")
async def get_invoices(_: None = Depends(verify_password)):
    """
    Return all invoices as JSON.
    This endpoint uses the same basic password verification as /process-mock-email.
    """
    return {"invoices": list_invoices()}


@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Render the login page.
    """
    error_code = request.query_params.get("error")
    error_message = LOGIN_ERROR_MESSAGES.get(error_code)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "error_message": error_message,
        },
    )


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    """
    Simple password-based login that stores an 'authenticated' flag in the session.
    """
    if is_rate_limited(
        request=request,
        action="login",
        max_requests=LOGIN_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    ):
        return RedirectResponse("/?error=rate_limited", status_code=302)

    if password != settings.AUTH_PASSWORD:
        return RedirectResponse("/?error=invalid_credentials", status_code=302)

    request.session["authenticated"] = True
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
    try:
        invoices = list_invoices()
    except Exception:
        invoices = []
        error_message = DASHBOARD_ERROR_MESSAGES["list_failed"]
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "invoices": invoices,
            "error_message": error_message,
            "success_message": success_message,
        },
    )


@app.get("/process-ui")
async def process_ui(request: Request):
    """
    Process the sample mock email from the UI and redirect back to the dashboard.
    """
    if not require_auth(request):
        return RedirectResponse("/?error=auth_required", status_code=302)

    try:
        data = parse_mock_email("examples/sample_invoice_email.txt")
    except Exception:
        return RedirectResponse("/dashboard?error=parse_failed", status_code=302)
    try:
        save_invoice(data)
    except Exception:
        return RedirectResponse("/dashboard?error=save_failed", status_code=302)
    return RedirectResponse("/dashboard?success=uploaded", status_code=302)


@app.post("/upload-invoice")
async def upload_invoice(request: Request, file: UploadFile = File(...)):
    """
    Upload an invoice email file (.txt, .eml, .msg, .pdf),
    parse it using the appropriate parser, and save to the database.
    """
    if not require_auth(request):
        return RedirectResponse("/?error=auth_required", status_code=302)
    if is_rate_limited(
        request=request,
        action="upload_invoice",
        max_requests=UPLOAD_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=UPLOAD_RATE_LIMIT_WINDOW_SECONDS,
    ):
        return RedirectResponse("/dashboard?error=rate_limited", status_code=302)
    if not file.filename:
        return RedirectResponse("/dashboard?error=no_file_name", status_code=302)

    # Save file temporarily
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, file.filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Decide parser based on file extension
    ext = file.filename.lower().split(".")[-1]

    try:
        if ext == "txt":
            data = parse_mock_email(file_path)
        elif ext == "eml":
            data = parse_eml_invoice(file_path)
        elif ext == "msg":
            data = parse_msg_invoice(file_path)
        elif ext == "pdf":
            data = parse_pdf_invoice(file_path)
        else:
            # Unsupported file type
            return RedirectResponse("/dashboard?error=unsupported", status_code=302)
    except Exception:
        return RedirectResponse("/dashboard?error=parse_failed", status_code=302)

    # Save parsed invoice data to the database
    try:
        save_invoice(data)
    except Exception:
        return RedirectResponse("/dashboard?error=save_failed", status_code=302)
    return RedirectResponse("/dashboard?success=uploaded", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    """
    Clear the session and redirect back to the login page.
    """
    request.session.clear()
    return RedirectResponse("/", status_code=302)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

