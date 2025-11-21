from fastapi import FastAPI, Depends
from app.security import verify_password
from app.services.email_parser import parse_mock_email
from app.services.invoice_service import save_invoice, list_invoices

from pathlib import Path

app = FastAPI(title="Email Invoice Automation Demo")

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
