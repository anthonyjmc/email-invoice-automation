# app/services/email_parser.py

import re
import email
import quopri
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional

import extract_msg

from app.services.azure_invoice_agent import extract_invoice_from_email


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

        return data

    except Exception:
        # Fallback: legacy regex-only parsing if Azure fails for any reason
        vendor_match = re.search(
            r"(Vendor|From|Supplier|Billed\s*To|Company|Sender):?\s*(.+)",
            text,
            re.IGNORECASE,
        )

        total_match = re.search(
            r"(Total|Total Amount Due|Amount\s*Due|Balance)[^0-9]*"
            r"(\d[\d,]*(?:\.\d{2})?)",
            text,
            re.IGNORECASE,
        )

        vendor = vendor_match.group(2).strip() if vendor_match else "Unknown Vendor"

        if total_match:
            raw_amount = total_match.group(2).replace(",", "")
            try:
                total = float(raw_amount)
            except ValueError:
                total = 0.0
        else:
            total = 0.0

        return {
            "vendor": vendor,
            "total": total,
            "currency": "USD",
            "invoice_date": datetime.today().date().isoformat(),
            "sender_email": fallback_sender or "unknown@email.com",
        }