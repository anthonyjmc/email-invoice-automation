from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

WebAuthProvider = Literal["legacy", "supabase"]

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """

    SESSION_SECRET: str = Field(
        min_length=32,
        description="Secret for signing session cookies. Use a long random value per environment.",
    )
    SESSION_MAX_AGE_SECONDS: int = Field(
        default=8 * 3600,
        ge=60,
        description="Browser session cookie lifetime (seconds).",
    )
    SESSION_COOKIE_SECURE: bool = Field(
        default=False,
        description="Set True behind HTTPS in production so the session cookie is Secure.",
    )
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = Field(
        default="lax",
        description="SameSite for session cookie. Use lax unless you need cross-site cookies.",
    )
    WEB_AUTH_PROVIDER: WebAuthProvider = Field(
        default="legacy",
        description="legacy = shared AUTH_PASSWORD; supabase = Supabase Auth email/password.",
    )
    APP_PASSWORD: str
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    AUTH_PASSWORD: str

    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_DEPLOYMENT: str

    MAX_UPLOAD_FILE_BYTES: int = Field(
        default=10 * 1024 * 1024,
        ge=1024,
        description="Maximum upload size in bytes (default 10 MB).",
    )
    UPLOAD_AV_SCAN_ENABLED: bool = Field(
        default=False,
        description="If true, run optional antivirus command after upload (see UPLOAD_AV_SCAN_COMMAND).",
    )
    UPLOAD_AV_SCAN_COMMAND: str | None = Field(
        default=None,
        description='Shell command with {path} placeholder, e.g. clamscan --no-summary {path}',
    )
    UPLOAD_AV_SCAN_TIMEOUT_SECONDS: int = Field(
        default=120,
        ge=5,
        description="Timeout for optional AV subprocess.",
    )
    UPLOAD_AV_SCAN_PDF_ONLY: bool = Field(
        default=True,
        description="When AV scan is enabled, only run it for .pdf uploads (recommended).",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()