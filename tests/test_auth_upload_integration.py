from __future__ import annotations

import re
from pathlib import Path

from starlette.testclient import TestClient


def _csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match is not None, html[:800]
    return match.group(1)


def test_login_success_redirects_to_dashboard(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    token = _csrf_token(r.text)
    r2 = client.post(
        "/login",
        data={"csrf_token": token, "password": "test-login-password"},
        follow_redirects=False,
    )
    assert r2.status_code == 302
    assert "/dashboard" in (r2.headers.get("location") or "")


def test_login_invalid_password_redirects_with_error(client: TestClient) -> None:
    r = client.get("/")
    token = _csrf_token(r.text)
    r2 = client.post(
        "/login",
        data={"csrf_token": token, "password": "wrong-password"},
        follow_redirects=False,
    )
    assert r2.status_code == 302
    assert "invalid_credentials" in (r2.headers.get("location") or "")


def test_upload_happy_path_txt_sample(client: TestClient) -> None:
    r = client.get("/")
    token = _csrf_token(r.text)
    client.post(
        "/login",
        data={"csrf_token": token, "password": "test-login-password"},
        follow_redirects=True,
    )
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    upload_csrf = _csrf_token(dash.text)
    sample_path = Path(__file__).resolve().parents[1] / "examples" / "sample_invoice_email.txt"
    raw = sample_path.read_bytes()
    up = client.post(
        "/upload-invoice",
        data={"csrf_token": upload_csrf},
        files={"file": ("invoice.txt", raw, "text/plain")},
        follow_redirects=False,
    )
    assert up.status_code == 302
    loc = up.headers.get("location", "")
    assert "success=uploaded" in loc


def test_upload_invalid_csrf_redirects(client: TestClient) -> None:
    r = client.get("/")
    token = _csrf_token(r.text)
    client.post(
        "/login",
        data={"csrf_token": token, "password": "test-login-password"},
        follow_redirects=True,
    )
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert len(_csrf_token(dash.text)) > 0
    sample_path = Path(__file__).resolve().parents[1] / "examples" / "sample_invoice_email.txt"
    raw = sample_path.read_bytes()
    up = client.post(
        "/upload-invoice",
        data={"csrf_token": "not-the-token"},
        files={"file": ("invoice.txt", raw, "text/plain")},
        follow_redirects=False,
    )
    assert up.status_code == 302
    assert "csrf_invalid" in (up.headers.get("location") or "")


def test_upload_unsupported_extension_redirects(client: TestClient) -> None:
    r = client.get("/")
    token = _csrf_token(r.text)
    client.post(
        "/login",
        data={"csrf_token": token, "password": "test-login-password"},
        follow_redirects=True,
    )
    dash = client.get("/dashboard")
    upload_csrf = _csrf_token(dash.text)
    up = client.post(
        "/upload-invoice",
        data={"csrf_token": upload_csrf},
        files={"file": ("malware.exe", b"MZ\x00\x00", "application/octet-stream")},
        follow_redirects=False,
    )
    assert up.status_code == 302
    assert "unsupported" in (up.headers.get("location") or "")
