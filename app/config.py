import logging
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WebAuthProvider = Literal["legacy", "supabase"]
LogFormat = Literal["text", "json"]

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
    SUPABASE_SERVICE_ROLE_KEY: str | None = Field(
        default=None,
        description="Server-only key; bypasses RLS. Use for legacy auth + RLS, or admin API. Never ship to the browser.",
    )
    AUTH_PASSWORD: str

    @field_validator("SUPABASE_SERVICE_ROLE_KEY", mode="before")
    @classmethod
    def empty_service_role_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

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

    REDIS_URL: str | None = Field(
        default=None,
        description="If set, rate limits use Redis (shared across workers). Example: redis://localhost:6379/0",
    )
    RATE_LIMIT_REDIS_KEY_PREFIX: str = Field(
        default="rl:v1",
        description="Prefix for Redis rate-limit keys.",
    )
    RATE_LIMIT_TRUST_X_FORWARDED_FOR: bool = Field(
        default=False,
        description="If True, use first X-Forwarded-For hop as client IP (set True behind a trusted reverse proxy).",
    )

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def empty_redis_url_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    SECURITY_HEADERS_ENABLED: bool = Field(
        default=True,
        description="Send security headers (CSP, X-Content-Type-Options, etc.) on every response.",
    )
    SECURITY_ENABLE_HSTS: bool = Field(
        default=False,
        description="Send Strict-Transport-Security. Enable only when the app is served over HTTPS (e.g. behind TLS-terminating proxy).",
    )
    SECURITY_HSTS_MAX_AGE: int = Field(default=31536000, ge=0, description="HSTS max-age in seconds (default 1 year).")
    SECURITY_HSTS_INCLUDE_SUBDOMAINS: bool = Field(default=True)
    SECURITY_HSTS_PRELOAD: bool = Field(
        default=False,
        description="Add preload directive only if you intend to submit the domain to the HSTS preload list.",
    )
    SECURITY_CSP: str | None = Field(
        default=None,
        description="Override Content-Security-Policy. If unset, a default compatible with inline Jinja templates is used.",
    )
    SECURITY_CSP_UPGRADE_INSECURE: bool = Field(
        default=False,
        description="Append upgrade-insecure-requests to CSP (useful behind TLS proxies).",
    )
    SECURITY_X_FRAME_OPTIONS: str = Field(default="DENY", description="X-Frame-Options value (DENY, SAMEORIGIN, etc.).")
    SECURITY_REFERRER_POLICY: str = Field(default="strict-origin-when-cross-origin")
    SECURITY_PERMISSIONS_POLICY: str = Field(
        default="camera=(), microphone=(), geolocation=(), payment=()",
        description="Permissions-Policy (Feature-Policy successor) sent to browsers.",
    )
    SECURITY_CROSS_ORIGIN_OPENER_POLICY: str | None = Field(
        default="same-origin",
        description="COOP header; set empty string to omit.",
    )

    @field_validator("SECURITY_CROSS_ORIGIN_OPENER_POLICY", mode="before")
    @classmethod
    def empty_coop_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    LOG_LEVEL: str = Field(
        default="INFO",
        description="Python log level (DEBUG, INFO, WARNING, ERROR).",
    )
    LOG_FORMAT: LogFormat = Field(
        default="text",
        description="text = human-readable console; json = one JSON object per line (log aggregators).",
    )
    OBSERVABILITY_METRICS_ENABLED: bool = Field(
        default=False,
        description="Expose Prometheus metrics at GET /metrics (enable in private networks or behind auth).",
    )
    OBSERVABILITY_ACCESS_LOG: bool = Field(
        default=True,
        description="Emit one structured log line per HTTP request (method, path, status, duration_ms, correlation_id).",
    )

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        if not isinstance(value, str):
            return "INFO"
        upper = value.upper()
        if hasattr(logging, upper) and isinstance(getattr(logging, upper), int):
            return upper
        return "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()