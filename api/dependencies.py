"""
API Dependencies

Dependency injection for services.
"""

import os
from functools import lru_cache

from smallcogs.services import (
    InventoryService,
    OrderService,
    VoiceService,
)

# Re-export verify_api_key as get_api_key for backwards compatibility
from api.middleware.auth import verify_api_key as get_api_key


class FileStorage:
    """Simple file storage for uploads."""

    def __init__(self, base_path: str = "./data/uploads"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    async def save_upload(self, file, dataset_id: str, filename: str) -> str:
        """Save an uploaded file."""
        dir_path = os.path.join(self.base_path, dataset_id)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, filename)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        return file_path


@lru_cache()
def get_file_storage() -> FileStorage:
    """Get file storage instance."""
    return FileStorage()


@lru_cache()
def get_inventory_service() -> InventoryService:
    """Get singleton inventory service."""
    return InventoryService(storage_path="./data")


@lru_cache()
def get_voice_service() -> VoiceService:
    """Get singleton voice service."""
    openai_key = os.environ.get("OPENAI_API_KEY")
    return VoiceService(openai_api_key=openai_key)


@lru_cache()
def get_order_service() -> OrderService:
    """Get singleton order service."""
    return OrderService()
