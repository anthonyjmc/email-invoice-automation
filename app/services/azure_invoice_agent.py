# app/services/azure_invoice_agent.py

from typing import Optional

from openai import AzureOpenAI
from pydantic import BaseModel

from app.config import settings  # <-- use Settings instead of os.environ


# Azure OpenAI client configured with endpoint + api_key from settings
client = AzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    api_version="2024-02-01",  # Adjust if your resource uses a different version
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
)

DEPLOYMENT_NAME = settings.AZURE_OPENAI_DEPLOYMENT


class InvoiceInfo(BaseModel):
    """Structured output model for invoice information extracted from emails."""
    vendor: Optional[str]
    total: Optional[float]
    currency: Optional[str]
    invoice_date: Optional[str]   # Ideally YYYY-MM-DD
    sender_email: Optional[str]


def extract_invoice_from_email(email_text: str) -> dict:
    """
    Use Azure OpenAI with structured outputs to extract invoice information
    from raw email text.
    """

    completion = client.beta.chat.completions.parse(
        model=DEPLOYMENT_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an assistant that reads invoice emails and extracts structured invoice data. "
                    "You MUST return only the fields defined in the schema: "
                    "vendor (supplier name), total (numeric amount), currency (e.g. 'USD'), "
                    "invoice_date (invoice date in YYYY-MM-DD if possible), "
                    "sender_email (email address of the sender if available). "
                    "If a value is missing or not clear, set it to null."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Read the following email and extract the invoice fields:\n\n"
                    f"{email_text}"
                ),
            },
        ],
        response_format=InvoiceInfo,
    )

    message = completion.choices[0].message

    if message.refusal is not None:
        raise RuntimeError(f"Model refused the request: {message.refusal}")

    parsed: InvoiceInfo = message.parsed
    data = parsed.model_dump(exclude_none=True)

    if "currency" not in data or data.get("currency") is None:
        data["currency"] = "USD"

    return data