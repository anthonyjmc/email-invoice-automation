from __future__ import annotations

from starlette.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("rate_limit_backend") == "memory"


def test_metrics_disabled_by_default(client: TestClient) -> None:
    r = client.get("/metrics")
    assert r.status_code == 404


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
