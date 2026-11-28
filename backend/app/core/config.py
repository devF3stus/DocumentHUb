from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    app_name: str = "DocumentHub API"
    app_version: str = "0.2.0"
    environment: str = "development"
    cors_origins: str = "http://localhost:3000"

    # Upload security limits
    max_upload_size_mb: int = 20
    max_pdf_pages: int = 100

    # Supabase (optional in local guest-only/test mode)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "documents"
    signed_url_expiry_seconds: int = 60

    # Independent AI Service (server-side only; never exposed to browser)
    ai_provider: str = "openrouter"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct:free"
    ai_timeout_seconds: float = 25.0
    ai_max_retries: int = 2
    ai_max_input_chars: int = 12000
    ai_daily_request_limit: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        """Return maximum allowed upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def supabase_configured(self) -> bool:
        """Return True when Supabase URL and service key are provided."""
        return bool(self.supabase_url.strip() and self.supabase_service_role_key.strip())


settings = Settings()
