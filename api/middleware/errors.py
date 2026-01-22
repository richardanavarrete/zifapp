"""Error handling middleware and exception handlers."""

import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("houndcogs.api")


class APIError(Exception):
    """Base class for API errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Dict[str, Any] = None
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(APIError):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} not found: {identifier}",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": identifier}
        )


class ValidationError(APIError):
    """Validation error."""

    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details or {}
        )


class ProcessingError(APIError):
    """Processing error (valid input, but processing failed)."""

    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(
            code="PROCESSING_ERROR",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details or {}
        )


class ConflictError(APIError):
    """Resource conflict (already exists)."""

    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details or {}
        )


def build_error_response(
    request: Request,
    code: str,
    message: str,
    status_code: int,
    details: Dict[str, Any] = None
) -> JSONResponse:
    """Build a standardized error response."""
    request_id = getattr(request.state, "request_id", "unknown")

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {}
            },
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )


def setup_exception_handlers(app: FastAPI):
    """Register exception handlers with the FastAPI app."""

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        """Handle custom API errors."""
        logger.warning(f"API Error: {exc.code} - {exc.message}")
        return build_error_response(
            request=request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors from request parsing."""
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })

        logger.warning(f"Validation Error: {errors}")
        return build_error_response(
            request=request,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"errors": errors}
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected errors."""
        logger.exception(f"Unexpected error: {str(exc)}")
        return build_error_response(
            request=request,
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"type": type(exc).__name__}
        )
