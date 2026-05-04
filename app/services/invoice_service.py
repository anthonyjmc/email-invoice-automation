from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any, Literal, TypedDict

from supabase import Client

from app.config import settings

ALLOWED_INVOICE_ROW_KEYS = frozenset(
    {
        "vendor",
        "total",
        "currency",
        "invoice_date",
        "sender_email",
        "invoice_number",
        "source_content_hash",
        "invoice_ref",
        "idempotency_key",
        "user_id",
    }
)


class SaveInvoiceResult(TypedDict):
    status: Literal["created", "duplicate"]
    id: str
    invoice: dict[str, Any]


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_invoice_ref(vendor: str | None, invoice_number: str | None, invoice_date: str | None) -> str | None:
    if not invoice_number or not str(invoice_number).strip():
        return None
    v = (vendor or "").strip().lower()[:200]
    n = str(invoice_number).strip().lower()[:120]
    d = (invoice_date or "").strip()[:32]
    ref = f"{v}|{n}|{d}"
    return ref if ref.strip("|") else None


def _normalize_row(data: dict[str, Any]) -> dict[str, Any]:
    row = {k: v for k, v in data.items() if k in ALLOWED_INVOICE_ROW_KEYS}
    if "invoice_date" in row and isinstance(row["invoice_date"], (date, datetime)):
        row["invoice_date"] = row["invoice_date"].isoformat()
    return row


def _find_by_content_hash(client: Client, *, user_id: str | None, h: str) -> dict[str, Any] | None:
    q = (
        client.table("invoices")
        .select("id,vendor,total,currency,invoice_date,sender_email,invoice_number,created_at,source_content_hash,invoice_ref")
        .eq("source_content_hash", h)
    )
    if user_id:
        q = q.eq("user_id", user_id)
    else:
        q = q.is_("user_id", "null")
    r = q.limit(1).execute()
    if r.data:
        return r.data[0]
    return None


def _find_by_invoice_ref(client: Client, *, user_id: str | None, ref: str) -> dict[str, Any] | None:
    if not user_id or not ref:
        return None
    r = (
        client.table("invoices")
        .select("id,vendor,total,currency,invoice_date,sender_email,invoice_number,created_at,source_content_hash,invoice_ref")
        .eq("user_id", user_id)
        .eq("invoice_ref", ref)
        .limit(1)
        .execute()
    )
    if r.data:
        return r.data[0]
    return None


def _find_by_idempotency_key(client: Client, *, user_id: str | None, key: str) -> dict[str, Any] | None:
    if not key or not key.strip():
        return None
    k = key.strip()[:256]
    q = (
        client.table("invoices")
        .select("id,vendor,total,currency,invoice_date,sender_email,invoice_number,created_at,source_content_hash,invoice_ref")
        .eq("idempotency_key", k)
    )
    if user_id:
        q = q.eq("user_id", user_id)
    else:
        q = q.is_("user_id", "null")
    r = q.limit(1).execute()
    if r.data:
        return r.data[0]
    return None


def save_invoice(
    data: dict[str, Any],
    *,
    client: Client,
    user_id: str | None = None,
    source_content_hash: str | None = None,
    idempotency_key: str | None = None,
) -> SaveInvoiceResult:
    row = _normalize_row(dict(data))
    if user_id is not None:
        row["user_id"] = user_id
    else:
        row.pop("user_id", None)

    inv_no = row.get("invoice_number")
    if isinstance(inv_no, str):
        inv_no = inv_no.strip() or None
        row["invoice_number"] = inv_no

    inv_ref = build_invoice_ref(row.get("vendor"), inv_no, row.get("invoice_date"))
    if inv_ref:
        row["invoice_ref"] = inv_ref
    if source_content_hash:
        row["source_content_hash"] = source_content_hash
    if idempotency_key and idempotency_key.strip():
        row["idempotency_key"] = idempotency_key.strip()[:256]

    existing = None
    if row.get("idempotency_key"):
        existing = _find_by_idempotency_key(client, user_id=user_id, key=row["idempotency_key"])
    if not existing and row.get("source_content_hash"):
        existing = _find_by_content_hash(client, user_id=user_id, h=row["source_content_hash"])
    if not existing and row.get("invoice_ref") and user_id:
        existing = _find_by_invoice_ref(client, user_id=user_id, ref=row["invoice_ref"])

    if existing:
        return {
            "status": "duplicate",
            "id": str(existing["id"]),
            "invoice": existing,
        }

    insert_payload = {k: v for k, v in row.items() if v is not None}
    try:
        ins = (
            client.table("invoices")
            .insert(insert_payload)
            .select("id,vendor,total,currency,invoice_date,sender_email,invoice_number,created_at")
            .execute()
        )
    except Exception as exc:
        msg = str(exc).lower()
        if "duplicate" in msg or "unique" in msg or "23505" in msg:
            if row.get("source_content_hash"):
                existing = _find_by_content_hash(client, user_id=user_id, h=row["source_content_hash"])
            if not existing and row.get("invoice_ref") and user_id:
                existing = _find_by_invoice_ref(client, user_id=user_id, ref=row["invoice_ref"])
            if not existing and row.get("idempotency_key"):
                existing = _find_by_idempotency_key(client, user_id=user_id, key=row["idempotency_key"])
            if existing:
                return {
                    "status": "duplicate",
                    "id": str(existing["id"]),
                    "invoice": existing,
                }
        raise

    created = (ins.data or [None])[0]
    if not created or not isinstance(created, dict):
        return {
            "status": "created",
            "id": "unknown",
            "invoice": insert_payload,
        }

    return {
        "status": "created",
        "id": str(created.get("id", "unknown")),
        "invoice": created,
    }


class ListInvoicesPage(TypedDict):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


def list_invoices(
    *,
    client: Client,
    limit: int = 50,
    offset: int = 0,
) -> ListInvoicesPage:
    limit = max(1, min(limit, settings.INVOICE_LIST_MAX_LIMIT))
    offset = max(0, offset)
    hi = offset + limit - 1
    resp = (
        client.table("invoices")
        .select("*", count="exact")
        .order("created_at", desc=True)
        .range(offset, hi)
        .execute()
    )
    items = resp.data or []
    total = resp.count if getattr(resp, "count", None) is not None else len(items)
    return {"items": items, "total": int(total), "limit": limit, "offset": offset}
