"""File management endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from api.dependencies import get_api_key, get_file_storage
from api.middleware.errors import NotFoundError

router = APIRouter()


@router.get("/{file_id}")
async def download_file(
    file_id: str,
    api_key: str = Depends(get_api_key),
    file_storage = Depends(get_file_storage),
):
    """
    Download a file by ID.

    Returns the file as a download with appropriate content type.
    Used for downloading generated reports, exports, etc.
    """
    try:
        # Get file info and path
        file_info = await file_storage.get_file_info(file_id)
        if not file_info:
            raise NotFoundError("File", file_id)

        file_path = file_info["path"]
        filename = file_info.get("filename", file_id)
        content_type = file_info.get("content_type", "application/octet-stream")

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=content_type,
        )

    except NotFoundError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve file: {str(e)}"
        )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    api_key: str = Depends(get_api_key),
    file_storage = Depends(get_file_storage),
):
    """
    Delete a file.

    Removes the file from storage. This is permanent.
    """
    try:
        success = await file_storage.delete_file(file_id)
        if not success:
            raise NotFoundError("File", file_id)

        return {
            "status": "deleted",
            "file_id": file_id,
            "deleted_at": datetime.utcnow().isoformat() + "Z"
        }

    except NotFoundError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


@router.get("/{file_id}/info")
async def get_file_info(
    file_id: str,
    api_key: str = Depends(get_api_key),
    file_storage = Depends(get_file_storage),
):
    """
    Get metadata about a file without downloading it.
    """
    file_info = await file_storage.get_file_info(file_id)
    if not file_info:
        raise NotFoundError("File", file_id)

    return {
        "file_id": file_id,
        "filename": file_info.get("filename"),
        "size_bytes": file_info.get("size"),
        "content_type": file_info.get("content_type"),
        "created_at": file_info.get("created_at"),
    }
