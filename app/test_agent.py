# test_agent.py
from dotenv import load_dotenv
load_dotenv()

from app.services.azure_invoice_agent import extract_invoice_from_email

sample_email = """
Vendor: ACME Corp
Total: $123.45
Currency: USD
Date: 2025-01-01
From: billing@acme.com

Dear customer,
This is your invoice for January.
"""

result = extract_invoice_from_email(sample_email)
print(result)
