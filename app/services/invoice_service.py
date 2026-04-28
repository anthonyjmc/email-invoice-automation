from app.db import supabase
from datetime import date, datetime

def save_invoice(data):
    # Normalize date values before persisting
    if "invoice_date" in data:
        if isinstance(data["invoice_date"], (date, datetime)):
            data["invoice_date"] = data["invoice_date"].isoformat()
        # If it is already a string, keep it unchanged

    supabase.table("invoices").insert(data).execute()

def list_invoices():
    return supabase.table("invoices").select("*").order("created_at", desc=True).execute().data
