import re
from datetime import datetime
from pathlib import Path

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
