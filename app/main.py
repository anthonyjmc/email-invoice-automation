import tempfile
import os
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
)
from app.services.invoice_service import save_invoice, list_invoices

load_dotenv()

templates = Jinja2Templates(directory="app/templates")
app = FastAPI(title="Email Invoice Automation Demo")

# NOTE: you should change this secret key in production
app.add_middleware(SessionMiddleware, secret_key="SUPER_SECRET_KEY_CHANGE_THIS")


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
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    """
    Simple password-based login that stores an 'authenticated' flag in the session.
    """
    if password != settings.AUTH_PASSWORD:
        return RedirectResponse("/", status_code=302)

    request.session["authenticated"] = True
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """
    Render the dashboard with all saved invoices.
    Requires the user to be authenticated via session.
    """
    if not require_auth(request):
        return RedirectResponse("/", status_code=302)

    invoices = list_invoices()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "invoices": invoices,
        },
    )


@app.get("/process-ui")
async def process_ui(request: Request):
    """
    Process the sample mock email from the UI and redirect back to the dashboard.
    """
    if not require_auth(request):
        return RedirectResponse("/", status_code=302)

    data = parse_mock_email("examples/sample_invoice_email.txt")
    save_invoice(data)
    return RedirectResponse("/dashboard", status_code=302)


@app.post("/upload-invoice")
async def upload_invoice(request: Request, file: UploadFile = File(...)):
    """
    Upload an invoice email file (.txt, .eml, .msg),
    parse it using the appropriate parser, and save to the database.
    """
    if not require_auth(request):
        return RedirectResponse("/", status_code=302)

    # Save file temporarily
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, file.filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Decide parser based on file extension
    ext = file.filename.lower().split(".")[-1]

    if ext == "txt":
        data = parse_mock_email(file_path)
    elif ext == "eml":
        data = parse_eml_invoice(file_path)
    elif ext == "msg":
        data = parse_msg_invoice(file_path)
    else:
        # Unsupported file type
        return RedirectResponse("/dashboard?error=unsupported", status_code=302)

    # Save parsed invoice data to the database
    save_invoice(data)
    return RedirectResponse("/dashboard", status_code=302)


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

