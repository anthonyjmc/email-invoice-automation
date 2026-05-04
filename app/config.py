from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """

    SESSION_SECRET: str = Field(
        min_length=32,
        description="Secret for signing session cookies. Use a long random value per environment.",
    )
    APP_PASSWORD: str
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    AUTH_PASSWORD: str

    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_DEPLOYMENT: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()