from fastapi import FastAPI, Depends
from app.security import verify_password
from app.services.email_parser import parse_mock_email
from app.services.invoice_service import save_invoice, list_invoices
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from .config import settings
from starlette.middleware.sessions import SessionMiddleware


from pathlib import Path

templates = Jinja2Templates(directory="app/templates")
app = FastAPI(title="Email Invoice Automation Demo")
app.add_middleware(SessionMiddleware, secret_key="SUPER_SECRET_KEY_CHANGE_THIS")


@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/process-mock-email")
async def process_mock_email(_: None = Depends(verify_password)):
    path = Path("examples/sample_invoice_email.txt")
    data = parse_mock_email(str(path))
    data["invoice_date"] = data["invoice_date"].isoformat()
    save_invoice(data)
    return {"status": "saved", "invoice": data}

@app.get("/invoices")
async def get_invoices(_: None = Depends(verify_password)):
    return {"invoices": list_invoices()}

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    if password != settings.auth_password:
        return RedirectResponse("/", status_code=302)

    request.session["authenticated"] = True
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not require_auth(request):
        return RedirectResponse("/", status_code=302)

    invoices = list_invoices()
    return templates.TemplateResponse("dashboard.html", {"request": request, "invoices": invoices})


@app.get("/process-ui")
async def process_ui(request: Request):
    if not require_auth(request):
        return RedirectResponse("/", status_code=302)

    data = parse_mock_email("examples/sample_invoice_email.txt")
    save_invoice(data)
    return RedirectResponse("/dashboard", status_code=302)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)

def require_auth(request: Request):
    if not request.session.get("authenticated"):
        return False
    return True


