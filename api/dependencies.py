"""FastAPI Dependency Injection."""

from typing import Generator, Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from api.config import get_settings, Settings

# API Key security scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    api_key: Optional[str] = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Validate API key from header.

    Returns the API key if valid, raises HTTPException otherwise.
    """
    # Allow if no API keys configured (development mode)
    if not settings.api_keys_list:
        return "dev-mode"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "API key required",
                    "details": {"header": "X-API-Key"}
                }
            }
        )

    if api_key not in settings.api_keys_list:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_API_KEY",
                    "message": "Invalid API key"
                }
            }
        )

    return api_key


def get_db():
    """
    Get database session.

    This will be a SQLite connection from houndcogs.storage.
    For now, returns a placeholder.
    """
    # TODO: Implement with houndcogs.storage.sqlite_repo
    from houndcogs.storage.sqlite_repo import get_connection

    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_file_storage():
    """
    Get file storage handler.

    Returns local file storage by default, can be swapped for S3.
    """
    # TODO: Implement with houndcogs.storage.file_storage
    from houndcogs.storage.file_storage import LocalFileStorage
    from api.config import get_settings

    settings = get_settings()
    return LocalFileStorage(
        upload_dir=settings.upload_dir,
        export_dir=settings.export_dir,
    )
