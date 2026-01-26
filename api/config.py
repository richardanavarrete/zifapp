"""
API Configuration

All secrets loaded from environment variables.
NEVER hardcode API keys, passwords, or secrets.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # App info
    app_name: str = "smallCOGS API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Security - API Keys (comma-separated list)
    api_keys: str = ""  # Loaded from API_KEYS env var

    # CORS
    cors_origins: str = "http://localhost:8501,http://localhost:3000"

    # Storage
    data_dir: str = "./data"
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 50

    # Database (for future use)
    database_url: Optional[str] = None  # e.g., sqlite:///./data/smallcogs.db

    # OpenAI (for voice transcription)
    openai_api_key: Optional[str] = None  # Loaded from OPENAI_API_KEY env var

    # Stripe (for billing)
    stripe_secret_key: Optional[str] = None  # Loaded from STRIPE_SECRET_KEY env var
    stripe_webhook_secret: Optional[str] = None  # Loaded from STRIPE_WEBHOOK_SECRET env var
    stripe_price_id_pro: Optional[str] = None  # Stripe Price ID for Pro tier ($49/mo)
    stripe_price_id_enterprise: Optional[str] = None  # Stripe Price ID for Enterprise tier ($199/mo)

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def api_key_list(self) -> List[str]:
        """Parse comma-separated API keys."""
        if not self.api_keys:
            return []
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def cors_origin_list(self) -> List[str]:
        """Parse comma-separated CORS origins."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
