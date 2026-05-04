from __future__ import annotations

from pathlib import Path

from app.services.email_parser import parse_mock_email


def test_parse_mock_email_sample_file_regex_fallback() -> None:
    """Azure is skipped in conftest; regex path fills vendor/total from examples file."""
    root = Path(__file__).resolve().parents[1]
    path = root / "examples" / "sample_invoice_email.txt"
    data = parse_mock_email(str(path))
    assert data.get("total") == 249.99
    assert data.get("currency") == "USD"
    assert data.get("vendor")
