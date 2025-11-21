from app.db import supabase

def save_invoice(data: dict):
    # Ensure invoice_date is a string (JSON-safe)
    if data.get("invoice_date"):
        data["invoice_date"] = data["invoice_date"].format()
    supabase.table("invoices").insert(data).execute()

def list_invoices():
    return supabase.table("invoices").select("*").order("created_at", desc=True).execute().data
