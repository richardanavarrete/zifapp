"""
Supabase Integration Module

Provides authentication, database, and storage integration with Supabase.
"""

from api.auth.errors import AuthError
from api.supabase.middleware import (
    get_current_user,
    get_current_user_optional,
    require_org,
    require_org_admin,
    require_org_owner,
)
from api.supabase.models import (
    AuthTokens,
    CurrentUser,
    LoginRequest,
    LoginResponse,
    Organization,
    OrganizationCreate,
    OrganizationMember,
    OrganizationRole,
    User,
    UserCreate,
    UserProfile,
)

__all__ = [
    # Auth Error
    "AuthError",
    # Middleware
    "get_current_user",
    "get_current_user_optional",
    "require_org",
    "require_org_admin",
    "require_org_owner",
    # Models
    "User",
    "UserCreate",
    "UserProfile",
    "Organization",
    "OrganizationCreate",
    "OrganizationMember",
    "OrganizationRole",
    "CurrentUser",
    "AuthTokens",
    "LoginRequest",
    "LoginResponse",
]


def __getattr__(name):
    """Lazy-load Supabase-specific imports to avoid errors when Supabase is not installed."""
    if name == "AuthService":
        from api.supabase.auth_service import AuthService
        return AuthService
    if name == "SupabaseRepository":
        from api.supabase.repository import SupabaseRepository
        return SupabaseRepository
    if name in ("get_supabase_client", "get_supabase_admin_client", "get_supabase_client_optional", "SupabaseClientError"):
        from api.supabase import client as _client
        return getattr(_client, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
