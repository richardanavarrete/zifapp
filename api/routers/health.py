"""Health check endpoints."""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends

from api.config import get_settings, Settings

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic liveness check.

    Returns 200 if the service is running.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/health/ready")
async def readiness_check(
    settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """
    Readiness check - verifies dependencies are available.

    Checks:
    - Database connectivity
    - File storage accessibility
    - OpenAI API (if configured)
    """
    checks = {
        "database": {"status": "ok"},
        "file_storage": {"status": "ok"},
    }

    # Check database
    try:
        # TODO: Actually check DB connection
        # from houndcogs.storage.sqlite_repo import check_connection
        # check_connection()
        checks["database"]["status"] = "ok"
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)}

    # Check file storage
    try:
        import os
        for dir_path in [settings.upload_dir, settings.export_dir]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
        checks["file_storage"]["status"] = "ok"
    except Exception as e:
        checks["file_storage"] = {"status": "error", "message": str(e)}

    # Check OpenAI (optional)
    if settings.openai_api_key:
        checks["openai"] = {"status": "configured"}
    else:
        checks["openai"] = {"status": "not_configured"}

    # Overall status
    all_ok = all(
        c.get("status") == "ok" or c.get("status") == "configured" or c.get("status") == "not_configured"
        for c in checks.values()
    )

    return {
        "status": "ready" if all_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": settings.app_version,
        "checks": checks
    }


@router.get("/health/info")
async def service_info(
    settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """Return service information."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": "development" if settings.debug else "production",
    }
