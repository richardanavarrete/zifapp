"""
Rate limiting middleware using slowapi.

Per-IP rate limiting with configurable limits via environment variables.
"""

import logging
from datetime import datetime, timezone

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from api.config import get_settings

logger = logging.getLogger("smallcogs.rate_limit")


def get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind a reverse proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def _create_limiter() -> Limiter:
    """Create and return a configured Limiter instance."""
    settings = get_settings()
    return Limiter(
        key_func=get_client_ip,
        default_limits=[settings.rate_limit_default],
        enabled=settings.rate_limit_enabled,
        storage_uri="memory://",
    )


limiter = _create_limiter()


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom 429 handler matching the project's error response format."""
    request_id = getattr(request.state, "request_id", "unknown")
    retry_after = getattr(exc, "retry_after", 60)

    logger.warning(
        "Rate limit exceeded for %s on %s %s",
        get_client_ip(request),
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(retry_after)},
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded: {exc.detail}",
            },
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
