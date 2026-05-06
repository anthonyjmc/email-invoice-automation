from __future__ import annotations

from pathlib import Path

from app.services.email_parser import parse_mock_email, parse_pdf_invoice


def test_parse_mock_email_sample_file_regex_fallback() -> None:
    """Azure is skipped in conftest; regex path fills vendor/total from examples file."""
    root = Path(__file__).resolve().parents[1]
    path = root / "examples" / "sample_invoice_email.txt"
    data = parse_mock_email(str(path))
    assert data.get("total") == 249.99
    assert data.get("currency") == "USD"
    assert data.get("vendor")
    assert data.get("invoice_number") == "1234"


def test_parse_pdf_invoice_sample_file_regex_fallback() -> None:
    """Azure is skipped in conftest; PDF text extraction + regex path should work."""
    root = Path(__file__).resolve().parents[1]
    path = root / "examples" / "sample_invoice.pdf"
    data = parse_pdf_invoice(str(path))
    assert data.get("vendor")
    assert data.get("sender_email") == "accountsreceivable@northernpacific-equipment.com"
    assert data.get("invoice_number") == "INV-NPE-2847-Q1"
    assert data.get("total") == 4376.90
