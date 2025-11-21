from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    app_password: str
    auth_password: str

    class Config:
        env_file = ".env"

settings = Settings()
