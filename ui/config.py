"""UI Configuration."""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class UISettings(BaseSettings):
    """UI settings loaded from environment variables."""

    # API connection
    api_base_url: str = "http://localhost:8000"
    api_key: str = ""

    # UI settings
    page_title: str = "HoundCOGS"
    page_icon: str = ""
    debug: bool = False

    # Timeouts (seconds)
    request_timeout: int = 30
    upload_timeout: int = 120

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = "UI_"


@lru_cache()
def get_settings() -> UISettings:
    """Get cached settings instance."""
    return UISettings()
