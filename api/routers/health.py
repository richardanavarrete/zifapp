"""Health check endpoints."""

from fastapi import APIRouter

from api.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Basic liveness check."""
    return {"status": "ok", "service": "smallCOGS API"}


@router.get("/health/ready")
async def readiness_check():
    """Readiness check with version info."""
    settings = get_settings()
    return {
        "status": "ok",
        "version": settings.app_version,
        "debug": settings.debug,
    }
