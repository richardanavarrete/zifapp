"""
File Storage

Handles file uploads, downloads, and temporary files.
Supports local storage with optional S3 backend.
"""

import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import UploadFile

logger = logging.getLogger(__name__)


class LocalFileStorage:
    """
    Local file system storage handler.

    Files are organized by dataset_id and type:
    - uploads/{dataset_id}/{filename}
    - exports/{export_id}/{filename}
    - temp/{temp_id}_{filename}
    """

    def __init__(
        self,
        upload_dir: str = "./data/uploads",
        export_dir: str = "./data/exports",
        temp_dir: Optional[str] = None,
    ):
        self.upload_dir = Path(upload_dir)
        self.export_dir = Path(export_dir)
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "houndcogs"

        # Ensure directories exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # In-memory file registry (would be database in production)
        self._file_registry: Dict[str, Dict[str, Any]] = {}

    async def save_upload(
        self,
        file: UploadFile,
        dataset_id: str,
        filename: Optional[str] = None,
    ) -> str:
        """
        Save an uploaded file.

        Args:
            file: FastAPI UploadFile
            dataset_id: Dataset to associate with
            filename: Optional filename override

        Returns:
            Path to saved file
        """
        filename = filename or file.filename
        file_id = f"f_{uuid.uuid4().hex[:12]}"

        # Create dataset directory
        dataset_dir = self.upload_dir / dataset_id
        dataset_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = dataset_dir / filename

        try:
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            # Register file
            self._file_registry[file_id] = {
                "path": str(file_path),
                "filename": filename,
                "dataset_id": dataset_id,
                "size": len(content),
                "content_type": file.content_type,
                "created_at": datetime.utcnow().isoformat(),
            }

            logger.info(f"Saved upload: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Failed to save upload: {e}")
            raise

    async def save_temp(
        self,
        file: UploadFile,
        prefix: str = "",
    ) -> str:
        """
        Save a file to temporary storage.

        Args:
            file: FastAPI UploadFile
            prefix: Optional filename prefix

        Returns:
            Path to temp file
        """
        suffix = Path(file.filename).suffix if file.filename else ""
        temp_name = f"{prefix}_{uuid.uuid4().hex[:8]}{suffix}"
        temp_path = self.temp_dir / temp_name

        try:
            content = await file.read()
            with open(temp_path, "wb") as f:
                f.write(content)

            logger.debug(f"Saved temp file: {temp_path}")
            return str(temp_path)

        except Exception as e:
            logger.error(f"Failed to save temp file: {e}")
            raise

    async def save_export(
        self,
        content: bytes,
        filename: str,
        export_id: Optional[str] = None,
    ) -> str:
        """
        Save an export file.

        Args:
            content: File content
            filename: Filename
            export_id: Optional export ID

        Returns:
            File ID for retrieval
        """
        file_id = f"e_{uuid.uuid4().hex[:12]}"
        export_id = export_id or file_id

        # Create export directory
        export_path = self.export_dir / export_id
        export_path.mkdir(parents=True, exist_ok=True)

        file_path = export_path / filename

        try:
            with open(file_path, "wb") as f:
                f.write(content)

            # Determine content type
            content_type = self._guess_content_type(filename)

            # Register file
            self._file_registry[file_id] = {
                "path": str(file_path),
                "filename": filename,
                "export_id": export_id,
                "size": len(content),
                "content_type": content_type,
                "created_at": datetime.utcnow().isoformat(),
            }

            logger.info(f"Saved export: {file_path}")
            return file_id

        except Exception as e:
            logger.error(f"Failed to save export: {e}")
            raise

    async def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata."""
        return self._file_registry.get(file_id)

    async def get_file_path(self, file_id: str) -> Optional[str]:
        """Get file path by ID."""
        info = self._file_registry.get(file_id)
        return info["path"] if info else None

    async def delete_file(self, file_id: str) -> bool:
        """Delete a file."""
        info = self._file_registry.get(file_id)
        if not info:
            return False

        try:
            path = Path(info["path"])
            if path.exists():
                path.unlink()

            del self._file_registry[file_id]
            logger.info(f"Deleted file: {file_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False

    async def cleanup_temp(self, max_age_hours: int = 24):
        """Clean up old temporary files."""
        import time

        now = time.time()
        max_age_seconds = max_age_hours * 3600

        for file_path in self.temp_dir.iterdir():
            if file_path.is_file():
                age = now - file_path.stat().st_mtime
                if age > max_age_seconds:
                    try:
                        file_path.unlink()
                        logger.debug(f"Cleaned up temp file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp file {file_path}: {e}")

    def _guess_content_type(self, filename: str) -> str:
        """Guess content type from filename."""
        ext = Path(filename).suffix.lower()
        content_types = {
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".csv": "text/csv",
            ".json": "application/json",
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
            ".webm": "audio/webm",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
        }
        return content_types.get(ext, "application/octet-stream")
