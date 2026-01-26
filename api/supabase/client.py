"""
Supabase Client

Singleton client for Supabase operations.
"""

import logging
from functools import lru_cache
from typing import Optional

from supabase import Client, create_client

from api.config import get_settings

logger = logging.getLogger(__name__)


class SupabaseClientError(Exception):
    """Error initializing Supabase client."""
    pass


@lru_cache()
def get_supabase_client() -> Client:
    """
    Get the Supabase client instance (singleton).

    Uses the anon key for client-side operations.
    """
    settings = get_settings()

    if not settings.supabase_url or not settings.supabase_anon_key:
        raise SupabaseClientError(
            "Supabase not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY."
        )

    client = create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
    )

    logger.info("Supabase client initialized")
    return client


@lru_cache()
def get_supabase_admin_client() -> Client:
    """
    Get the Supabase admin client (service role).

    Uses the service role key for admin operations like creating users.
    WARNING: Never expose this client to end users.
    """
    settings = get_settings()

    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise SupabaseClientError(
            "Supabase admin not configured. Set SUPABASE_SERVICE_ROLE_KEY."
        )

    client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )

    logger.info("Supabase admin client initialized")
    return client


def get_supabase_client_optional() -> Optional[Client]:
    """
    Get Supabase client if configured, None otherwise.

    Useful for gradual migration where Supabase is optional.
    """
    settings = get_settings()

    if not settings.supabase_enabled:
        return None

    try:
        return get_supabase_client()
    except SupabaseClientError:
        return None
