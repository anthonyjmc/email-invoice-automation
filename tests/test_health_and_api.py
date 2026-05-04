from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.config import settings


def test_health_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("rate_limit_backend") == "memory"


def test_metrics_disabled_by_default(client: TestClient) -> None:
    r = client.get("/metrics")
    assert r.status_code == 404


def test_metrics_requires_bearer_when_token_configured(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(settings, "OBSERVABILITY_METRICS_ENABLED", True)
    monkeypatch.setattr(settings, "METRICS_BEARER_TOKEN", "metrics-secret-token")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = client.get("/metrics", headers={"Authorization": "Bearer metrics-secret-token"})
    assert ok.status_code == 200
    assert b"http_server_requests" in ok.content or b"# HELP" in ok.content


def test_metrics_no_bearer_when_token_unset(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(settings, "OBSERVABILITY_METRICS_ENABLED", True)
    monkeypatch.setattr(settings, "METRICS_BEARER_TOKEN", None)
    r = client.get("/metrics")
    assert r.status_code == 200


def test_csp_uses_script_nonce_when_enabled(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(settings, "SECURITY_CSP_USE_NONCES", True)
    monkeypatch.setattr(settings, "SECURITY_CSP", None)
    r = client.get("/")
    assert r.status_code == 200
    csp = r.headers.get("content-security-policy", "")
    assert "script-src" in csp
    assert "nonce-" in csp
    script_src_segment = csp.split("script-src", 1)[1].split(";", 1)[0]
    assert "unsafe-inline" not in script_src_segment


def test_process_mock_email_requires_app_password(client: TestClient) -> None:
    r = client.post("/process-mock-email")
    assert r.status_code == 401


def test_process_mock_email_with_valid_header(client: TestClient) -> None:
    r = client.post(
        "/process-mock-email",
        headers={"X-App-Password": "test-app-password"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") in ("created", "duplicate")
    assert "invoice" in data
    assert data["invoice"].get("total") == 249.99


def test_process_mock_email_accepts_bearer_token(client: TestClient) -> None:
    r = client.post(
        "/process-mock-email",
        headers={"Authorization": "Bearer test-app-password"},
    )
    assert r.status_code == 200
    assert r.json().get("status") in ("created", "duplicate")
