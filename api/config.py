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

    # JWT (standalone, used when Supabase is not configured)
    jwt_secret: str = ""  # Loaded from JWT_SECRET env var

    # Supabase
    supabase_url: Optional[str] = None  # Loaded from SUPABASE_URL env var
    supabase_anon_key: Optional[str] = None  # Loaded from SUPABASE_ANON_KEY env var
    supabase_service_role_key: Optional[str] = None  # Loaded from SUPABASE_SERVICE_ROLE_KEY env var
    supabase_jwt_secret: Optional[str] = None  # Loaded from SUPABASE_JWT_SECRET env var

    # OpenAI (for voice transcription)
    openai_api_key: Optional[str] = None  # Loaded from OPENAI_API_KEY env var

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

    @property
    def jwt_secret_key(self) -> str:
        """Return JWT signing key. Falls back to supabase secret or a dev default."""
        if self.jwt_secret:
            return self.jwt_secret
        if self.supabase_jwt_secret:
            return self.supabase_jwt_secret
        import hashlib
        import logging
        logging.getLogger("smallcogs").warning(
            "No JWT_SECRET set — using insecure dev default. Set JWT_SECRET in production."
        )
        return hashlib.sha256(b"smallcogs-dev-secret-change-me").hexdigest()

    @property
    def supabase_enabled(self) -> bool:
        """Check if Supabase is configured."""
        return bool(self.supabase_url and self.supabase_anon_key)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
