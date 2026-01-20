"""
API Dependencies

Dependency injection for services.
"""

import os
from functools import lru_cache

from smallcogs.services import (
    InventoryService,
    VoiceService,
    OrderService,
)


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
