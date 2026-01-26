"""
Supabase Integration Module

Provides authentication, database, and storage integration with Supabase.
"""

from api.supabase.auth_service import AuthError, AuthService
from api.supabase.client import (
    SupabaseClientError,
    get_supabase_admin_client,
    get_supabase_client,
    get_supabase_client_optional,
)
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
from api.supabase.repository import SupabaseRepository

__all__ = [
    # Client
    "get_supabase_client",
    "get_supabase_admin_client",
    "get_supabase_client_optional",
    "SupabaseClientError",
    # Auth Service
    "AuthService",
    "AuthError",
    # Middleware
    "get_current_user",
    "get_current_user_optional",
    "require_org",
    "require_org_admin",
    "require_org_owner",
    # Repository
    "SupabaseRepository",
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
