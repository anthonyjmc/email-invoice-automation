# app/services/email_parser.py

import re
import email
import quopri
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional

import extract_msg
from pypdf import PdfReader

from app.services.azure_invoice_agent import extract_invoice_from_email


def _extract_sender_email_from_text(text: str) -> Optional[str]:
    # Accept lines like:
    #   From: billing@vendor.com
    #   From: Accounts Receivable <billing@vendor.com>
    m = re.search(r"(?im)^\s*from\s*:\s*(.*?)\s*$", text)
    if not m:
        return None
    candidate = m.group(1).strip()
    if not candidate:
        # Some PDF text extractors split "From:" and the email onto the next line.
        m2 = re.search(r"(?im)^\s*from\s*:\s*$\s*([^\r\n]+)\s*$", text)
        candidate = m2.group(1).strip() if m2 else ""
    email_match = re.search(r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", candidate, re.IGNORECASE)
    return email_match.group(1) if email_match else None


def _extract_labeled_amount(text: str, *, label_pattern: str) -> float | None:
    """
    Extract a number that may appear on the same line as the label or on the next line.
    label_pattern should match the label without trailing punctuation (case-insensitive).
    """
    same_line = re.search(
        rf"(?im)^\s*(?:{label_pattern})\s*[:\-]?\s*[^0-9]*"
        rf"(\d[\d,]*(?:\.\d{{2}})?)\s*(?:USD|EUR|GBP)?\s*$",
        text,
    )
    if same_line:
        raw = same_line.group(1).replace(",", "")
        try:
            return float(raw)
        except ValueError:
            return None
    next_line = re.search(
        rf"(?im)^\s*(?:{label_pattern})\s*[:\-]?\s*$\s*"
        rf"(\d[\d,]*(?:\.\d{{2}})?)\s*(?:USD|EUR|GBP)?\s*$",
        text,
    )
    if not next_line:
        return None
    raw = next_line.group(1).replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def extract_invoice_number_from_text(text: str) -> Optional[str]:
    # Prefer explicit "Invoice Number" label (same or next line)
    m0 = re.search(r"(?im)^\s*invoice\s*number\s*:\s*([A-Za-z0-9][A-Za-z0-9\-]{2,})\s*$", text)
    if m0:
        return m0.group(1).strip()
    m0b = re.search(r"(?im)^\s*invoice\s*number\s*:\s*$\s*([A-Za-z0-9][A-Za-z0-9\-]{2,})\s*$", text)
    if m0b:
        return m0b.group(1).strip()

    m = re.search(
        r"(?im)subject\s*:\s*.*?invoice\s*#?\s*([A-Za-z0-9][A-Za-z0-9\-]*)",
        text,
    )
    if m:
        return m.group(1).strip()
    # Common explicit patterns: "Invoice # INV-123", "INV-123", "Invoice: INV-123"
    m2 = re.search(r"(?im)^\s*invoice\s*#?\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-]{2,})\s*$", text)
    if m2:
        return m2.group(1).strip()
    m3 = re.search(r"(?i)\bINV-[A-Za-z0-9][A-Za-z0-9\-]{2,}\b", text)
    if m3:
        return m3.group(0).strip()
    return None


def parse_msg_invoice(filepath: str) -> Dict[str, Any]:
    """
    Parse a .msg (Outlook) file and extract invoice fields using Azure OpenAI.

    If the file is not a valid .msg (e.g. a plain text file renamed with .msg),
    fall back to reading it as plain text.
    """
    try:
        msg = extract_msg.Message(filepath)
        body = msg.body or ""
        sender = msg.sender or None
        return parse_text_to_fields(body, fallback_sender=sender)
    except Exception:
        # Fallback: treat the file as a simple text file
        try:
            content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            content = ""
        return parse_text_to_fields(content)


def parse_eml_invoice(filepath: str) -> Dict[str, Any]:
    """
    Parse an .eml file and extract invoice fields using Azure OpenAI.
    """
    with open(filepath, "rb") as f:
        msg = email.message_from_bytes(f.read())

    body_parts: list[str] = []

    # Collect all text/plain parts
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    body_parts.append(
                        payload.decode(charset, errors="ignore")
                    )
    else:
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            charset = msg.get_content_charset() or "utf-8"
            body_parts.append(payload.decode(charset, errors="ignore"))
        elif isinstance(payload, str):
            body_parts.append(payload)

    body = "\n".join(body_parts)

    # Try to decode quoted-printable if needed
    try:
        body = quopri.decodestring(body).decode("utf-8", errors="ignore")
    except Exception:
        # If decoding fails, keep the original body
        pass

    sender = msg.get("From")

    return parse_text_to_fields(body, fallback_sender=sender)


def parse_mock_email(path: str) -> Dict[str, Any]:
    """
    Parse a plain text file used as a mock email.
    This is helpful for testing without real .eml or .msg files.
    """
    content = Path(path).read_text(encoding="utf-8", errors="ignore")
    return parse_text_to_fields(content)


def parse_pdf_invoice(filepath: str) -> Dict[str, Any]:
    """
    Parse a .pdf invoice by extracting text from all pages and then reusing
    the same invoice-field extraction pipeline.
    """
    try:
        reader = PdfReader(filepath)
        pages_text = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            pages_text.append(page_text)
        content = "\n".join(pages_text).strip()
    except Exception:
        content = ""

    return parse_text_to_fields(content, fallback_sender=_extract_sender_email_from_text(content))


def parse_text_to_fields(
    text: str,
    fallback_sender: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Central helper that:
    1) Calls Azure OpenAI to extract invoice fields using structured outputs.
    2) Complements or falls back to simple regex parsing if Azure
       fails or returns partial data.

    This function guarantees that:
    - 'total' is always a float (default 0.0)
    - 'invoice_date' is always a string (default today's date in ISO)
    - 'vendor', 'currency', 'sender_email' always have some value
    """

    # First, try Azure OpenAI structured output
    try:
        data = extract_invoice_from_email(text)

        # ---------- VENDOR ----------
        if not data.get("vendor"):
            vendor_match = re.search(
                r"(Vendor|From|Supplier|Billed\s*To|Company|Sender):?\s*(.+)",
                text,
                re.IGNORECASE,
            )
            if vendor_match:
                data["vendor"] = vendor_match.group(2).strip()

        # ---------- TOTAL ----------
        if data.get("total") is None:
            # This regex handles things like:
            # "Total: $249.99", "Total Amount Due: 249.99 USD", "Amount Due 1,299.00"
            total_match = re.search(
                r"(Total|Total Amount Due|Amount\s*Due|Balance)[^0-9]*"
                r"(\d[\d,]*(?:\.\d{2})?)",
                text,
                re.IGNORECASE,
            )
            if total_match:
                raw_amount = total_match.group(2)
                raw_amount = raw_amount.replace(",", "")  # remove thousand separators
                try:
                    data["total"] = float(raw_amount)
                except ValueError:
                    data["total"] = 0.0

        # If the model (or fallback regex) returned a subtotal-like number,
        # prefer an explicit "total due" line, or compute subtotal + tax when available.
        total_due = _extract_labeled_amount(
            text, label_pattern=r"Total\s*Amount\s*Due|Balance\s*Due|Amount\s*Due|Total"
        )
        subtotal = _extract_labeled_amount(text, label_pattern=r"Subtotal")
        tax = _extract_labeled_amount(text, label_pattern=r"(?:Sales\s*Tax|Tax)")

        if isinstance(data.get("total"), (int, float)):
            current_total = float(data["total"])
            if total_due is not None and abs(current_total - total_due) >= 0.01:
                data["total"] = total_due
            elif subtotal is not None and tax is not None and abs(current_total - subtotal) < 0.01:
                data["total"] = round(subtotal + tax, 2)

        # ---------- INVOICE DATE ----------
        if not data.get("invoice_date"):
            # Try ISO-style date: 2025-01-20
            date_match = re.search(
                r"(Invoice\s*Date|Date)[^\d]*(\d{4}-\d{2}-\d{2})",
                text,
                re.IGNORECASE,
            )

            # Or formats like "January 15, 2025"
            if not date_match:
                date_match = re.search(
                    r"(Invoice\s*Date|Date)[:\s]*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
                    text,
                    re.IGNORECASE,
                )

            if date_match:
                # Just store the raw date string for now
                data["invoice_date"] = date_match.group(2).strip()

        # ---------- SENDER EMAIL ----------
        if fallback_sender and not data.get("sender_email"):
            data["sender_email"] = fallback_sender
        if not data.get("sender_email"):
            inferred = _extract_sender_email_from_text(text)
            if inferred:
                data["sender_email"] = inferred

        # ---------- DEFAULTS ----------
        if not data.get("currency"):
            data["currency"] = "USD"

        if not data.get("invoice_date"):
            # If still missing, default to today's date in ISO format
            data["invoice_date"] = datetime.today().date().isoformat()

        if not data.get("vendor"):
            data["vendor"] = "Unknown Vendor"

        if data.get("total") is None:
            data["total"] = 0.0

        if not data.get("sender_email"):
            data["sender_email"] = "unknown@email.com"

        if not data.get("invoice_number"):
            inv = extract_invoice_number_from_text(text)
            if inv:
                data["invoice_number"] = inv

        return data

    except Exception:
        # Fallback: legacy regex-only parsing if Azure fails for any reason
        vendor_match = re.search(
            r"(Vendor|From|Supplier|Billed\s*To|Company|Sender):?\s*(.+)",
            text,
            re.IGNORECASE,
        )

        vendor = vendor_match.group(2).strip() if vendor_match else "Unknown Vendor"
        total_due = _extract_labeled_amount(
            text, label_pattern=r"Total\s*Amount\s*Due|Balance\s*Due|Amount\s*Due|Total"
        )
        subtotal = _extract_labeled_amount(text, label_pattern=r"Subtotal")
        tax = _extract_labeled_amount(text, label_pattern=r"(?:Sales\s*Tax|Tax)")
        if total_due is not None:
            total = total_due
        elif subtotal is not None and tax is not None:
            total = round(subtotal + tax, 2)
        else:
            total = 0.0

        inv = extract_invoice_number_from_text(text)
        inferred_sender = _extract_sender_email_from_text(text)
        out: Dict[str, Any] = {
            "vendor": vendor,
            "total": total,
            "currency": "USD",
            "invoice_date": datetime.today().date().isoformat(),
            "sender_email": fallback_sender or inferred_sender or "unknown@email.com",
        }
        if inv:
            out["invoice_number"] = inv
        return out