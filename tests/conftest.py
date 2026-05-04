"""
Test environment and shared fixtures. Env must be set before importing `app.main`.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

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

# Overwrite (not setdefault): host env must not break CI or local pytest.
for _key, _val in _TEST_ENV.items():
    os.environ[_key] = _val

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_supabase_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = MagicMock()
    mock.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[])
    mock.table.return_value.insert.return_value.execute.return_value = MagicMock()
    monkeypatch.setattr("app.main.get_supabase_for_request", lambda _req: mock)
    monkeypatch.setattr("app.main.get_supabase_for_api", lambda: mock)


@pytest.fixture(autouse=True)
def skip_azure_in_parser_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_azure(_email_text: str) -> None:
        raise RuntimeError("tests skip live Azure OpenAI")

    monkeypatch.setattr(
        "app.services.email_parser.extract_invoice_from_email",
        _no_azure,
    )
