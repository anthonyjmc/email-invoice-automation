from datetime import date, datetime

from supabase import Client


def save_invoice(data: dict, *, client: Client, user_id: str | None = None) -> None:
    # Normalize date values before persisting
    row = dict(data)
    if "invoice_date" in row:
        if isinstance(row["invoice_date"], (date, datetime)):
            row["invoice_date"] = row["invoice_date"].isoformat()

    if user_id is not None:
        row["user_id"] = user_id

    client.table("invoices").insert(row).execute()


def list_invoices(*, client: Client) -> list:
    response = client.table("invoices").select("*").order("created_at", desc=True).execute()
    return response.data or []
