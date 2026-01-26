"""
API Dependencies

Dependency injection for services.
"""

import os
from functools import lru_cache
from typing import Optional
from uuid import UUID

from fastapi import Depends

from api.config import get_settings
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


# =============================================================================
# Supabase Dependencies
# =============================================================================

def get_supabase_repository(org_id: UUID):
    """
    Get Supabase repository scoped to an organization.

    This is a factory function - call it with org_id to get a repo instance.
    Use in endpoints like:
        repo = get_supabase_repository(current_user.org_id)
    """
    from api.supabase.repository import SupabaseRepository
    return SupabaseRepository(org_id)


def get_repository_for_user(current_user):
    """
    Get repository for the current user's organization.

    Convenience function for use in endpoints:
        repo = get_repository_for_user(current_user)
    """
    if not current_user.org_id:
        return None
    return get_supabase_repository(current_user.org_id)


@lru_cache()
def get_auth_service():
    """Get singleton auth service."""
    settings = get_settings()

    if not settings.supabase_enabled:
        return None

    from api.supabase.auth_service import AuthService
    return AuthService()
