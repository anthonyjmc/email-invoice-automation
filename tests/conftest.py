"""
Test environment and shared fixtures. Env must be set before importing `app.main`.
"""

from __future__ import annotations

import os
from copy import deepcopy

import pytest
from starlette.testclient import TestClient

# Supabase demo-style JWT (syntactic); no network required until HTTP calls.
_ANON_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9."
    "CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
)

_TEST_ENV: dict[str, str] = {
    "SESSION_SECRET": "0" * 40,
    "APP_PASSWORD": "test-app-password",
    "SUPABASE_URL": "https://testproject.supabase.co",
    "SUPABASE_ANON_KEY": _ANON_JWT,
    "AUTH_PASSWORD": "test-login-password",
    "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
    "AZURE_OPENAI_API_KEY": "test-azure-key",
    "AZURE_OPENAI_DEPLOYMENT": "gpt-4o-mini",
    "WEB_AUTH_PROVIDER": "legacy",
    "REDIS_URL": "",
    "SESSION_COOKIE_SECURE": "false",
    "OBSERVABILITY_METRICS_ENABLED": "false",
    "LOG_FORMAT": "text",
}

for _key, _val in _TEST_ENV.items():
    os.environ[_key] = _val

from app.main import app  # noqa: E402
from app.services.invoice_service import build_invoice_ref  # noqa: E402

_INVOICE_ROWS: list[dict] = []


def _fake_save_invoice(
    data: dict,
    *,
    client,
    user_id: str | None = None,
    source_content_hash: str | None = None,
    idempotency_key: str | None = None,
):
    row = {k: v for k, v in deepcopy(data).items() if k != "id"}
    if user_id is not None:
        row["user_id"] = user_id
    if source_content_hash:
        row["source_content_hash"] = source_content_hash
    if idempotency_key:
        row["idempotency_key"] = idempotency_key
    inv_no = row.get("invoice_number")
    if isinstance(inv_no, str):
        inv_no = inv_no.strip() or None
        row["invoice_number"] = inv_no
    ref = build_invoice_ref(row.get("vendor"), inv_no, row.get("invoice_date"))
    if ref:
        row["invoice_ref"] = ref

    for existing in _INVOICE_ROWS:
        if idempotency_key and existing.get("idempotency_key") == idempotency_key:
            if existing.get("user_id") == user_id:
                return {"status": "duplicate", "id": str(existing["id"]), "invoice": existing}
        if source_content_hash and existing.get("source_content_hash") == source_content_hash:
            if existing.get("user_id") == user_id:
                return {"status": "duplicate", "id": str(existing["id"]), "invoice": existing}
        if ref and user_id and existing.get("invoice_ref") == ref and existing.get("user_id") == user_id:
            return {"status": "duplicate", "id": str(existing["id"]), "invoice": existing}

    row["id"] = str(len(_INVOICE_ROWS) + 1)
    _INVOICE_ROWS.append(row)
    return {"status": "created", "id": row["id"], "invoice": row}


def _fake_list_invoices(*, client, limit: int = 50, offset: int = 0):
    rev = list(reversed(_INVOICE_ROWS))
    total = len(rev)
    items = rev[offset : offset + limit]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


async def _rate_limit_disabled(*_a, **_k) -> bool:
    return False


@pytest.fixture(autouse=True)
def disable_rate_limits_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.check_rate_limited", _rate_limit_disabled)


@pytest.fixture(autouse=True)
def stub_invoice_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    _INVOICE_ROWS.clear()
    monkeypatch.setattr("app.main.save_invoice", _fake_save_invoice)
    monkeypatch.setattr("app.main.list_invoices", _fake_list_invoices)


@pytest.fixture(autouse=True)
def skip_azure_in_parser_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_azure(_email_text: str) -> None:
        raise RuntimeError("tests skip live Azure OpenAI")

    monkeypatch.setattr(
        "app.services.email_parser.extract_invoice_from_email",
        _no_azure,
    )
