"""
Authentication Middleware

API key validation for protected endpoints.
"""

import secrets
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from api.config import get_settings

# API key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header)
) -> str:
    """
    Verify API key from request header.

    Returns the API key if valid.
    Raises HTTPException if invalid or missing.
    """
    settings = get_settings()

    # Skip auth in debug mode if no keys configured
    if settings.debug and not settings.api_key_list:
        return "debug-mode"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "API key required. Include X-API-Key header.",
                }
            },
        )

    # Use constant-time comparison to prevent timing attacks
    valid = False
    for valid_key in settings.api_key_list:
        if secrets.compare_digest(api_key, valid_key):
            valid = True
            break

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_API_KEY",
                    "message": "Invalid API key.",
                }
            },
        )

    return api_key


def generate_api_key(prefix: str = "sc") -> str:
    """Generate a new API key."""
    import secrets
    return f"{prefix}_{secrets.token_urlsafe(24)}"
