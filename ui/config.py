"""UI Configuration - loads from environment variables."""

import os


class UIConfig:
    """UI configuration from environment."""

    # API connection
    API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
    API_KEY = os.environ.get("API_KEY", "")

    # UI settings
    PAGE_TITLE = "smallCOGS"
    PAGE_ICON = "📦"

    # Feature flags
    SHOW_DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
