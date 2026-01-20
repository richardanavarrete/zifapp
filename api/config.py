"""API Configuration."""

import os
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App info
    app_name: str = "HoundCOGS API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # API Keys (comma-separated list)
    api_keys: str = ""

    # Database
    database_url: str = "sqlite:///./data/db/houndcogs.db"

    # File storage
    upload_dir: str = "./data/uploads"
    export_dir: str = "./data/exports"
    cache_dir: str = "./data/cache"
    max_upload_size_mb: int = 50

    # OpenAI (for Whisper API)
    openai_api_key: Optional[str] = None

    # CORS
    cors_origins: str = "*"  # Comma-separated, or "*" for all

    # Rate limiting (requests per minute)
    rate_limit_rpm: int = 60

    # Background jobs (optional Redis URL)
    redis_url: Optional[str] = None

    # Logging
    log_level: str = "INFO"

    @property
    def api_keys_list(self) -> List[str]:
        """Parse API keys from comma-separated string."""
        if not self.api_keys:
            return []
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
