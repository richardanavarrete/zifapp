"""Request logging middleware."""

import logging
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("houndcogs.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all requests with timing and request ID.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Start timing
        start_time = time.perf_counter()

        # Log request
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - Started"
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"[{request_id}] {request.method} {request.url.path} - "
                f"Error after {duration:.2f}ms: {str(e)}"
            )
            raise

        # Calculate duration
        duration = (time.perf_counter() - start_time) * 1000

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{duration:.2f}"

        # Log response
        log_level = logging.INFO if response.status_code < 400 else logging.WARNING
        logger.log(
            log_level,
            f"[{request_id}] {request.method} {request.url.path} - "
            f"{response.status_code} in {duration:.2f}ms"
        )

        return response


def get_request_id(request: Request) -> str:
    """Get the request ID from the current request."""
    return getattr(request.state, "request_id", "unknown")
