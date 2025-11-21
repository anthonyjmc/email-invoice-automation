import re
from pathlib import Path
from email import message_from_string
import extract_msg
from datetime import date, datetime
import email
import quopri


def parse_msg_invoice(filepath: str):
    msg = extract_msg.Message(filepath)
    body = msg.body or ""  # 👈 FIX: asegura que nunca sea None
    return parse_text_to_fields(body)


def parse_eml_invoice(filepath: str):
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        raw_email = f.read()

    msg = email.message_from_string(raw_email)

    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    # Decodifica quoted-printable
                    body = quopri.decodestring(payload).decode("utf-8", errors="ignore")
                    break
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

    print("📨 Extracted EML body:\n", body)  # Debug

    return parse_text_to_fields(body)


def parse_text_to_fields(text: str):
    # Detect Vendor
    vendor_match = re.search(
        r"(Vendor|From|Supplier|Billed\s*To|Company|Sender):?\s*(.+)",
        text,
        re.IGNORECASE
    )

    # Detect Total Invoice Amount
    total_match = re.search(
        r"(Total|Amount\s*Due|Balance):?\s*\$?(\d+(?:\.\d{2})?)",
        text,
        re.IGNORECASE
    )

    vendor = vendor_match.group(2).strip() if vendor_match else "Unknown Vendor"
    total = float(total_match.group(2)) if total_match else 0.0

    return {
        "vendor": vendor,
        "total": total,
        "currency": "USD",
        "invoice_date": datetime.today().isoformat(),
        "sender_email": "unknown@email.com",
    }


def parse_mock_email(path: str) -> dict:
    content = Path(path).read_text()

    vendor = re.search(r"Vendor:\s*(.*)", content)
    total = re.search(r"Total:\s*([\d\.]+)\s*([A-Z]{3})", content)
    date = re.search(r"Date:\s*([\d\-]+)", content)
    sender = re.search(r"From:\s*(.*)", content)

    return {
        "sender_email": sender.group(1).strip() if sender else None,
        "vendor": vendor.group(1).strip() if vendor else None,
        "total": float(total.group(1)) if total else None,
        "currency": total.group(2) if total else None,
        "invoice_date": datetime.fromisoformat(date.group(1)).date() if date else None,
    }
