from app.db import supabase
from datetime import date, datetime

def save_invoice(data):
    # Normalizar fecha
    if "invoice_date" in data:
        if isinstance(data["invoice_date"], (date, datetime)):
            data["invoice_date"] = data["invoice_date"].isoformat()
        # else: ya es string → OK, no tocarlo

    supabase.table("invoices").insert(data).execute()

def list_invoices():
    return supabase.table("invoices").select("*").order("created_at", desc=True).execute().data
