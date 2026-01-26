"""
Supabase Auth Middleware

JWT token validation and user context injection for FastAPI.
"""

import logging
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.config import get_settings
from api.supabase.auth_service import AuthError, AuthService
from api.supabase.models import CurrentUser

logger = logging.getLogger(__name__)

# Bearer token security scheme
bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache()
def get_auth_service() -> AuthService:
    """Get singleton auth service."""
    return AuthService()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> CurrentUser:
    """
    Dependency to get the current authenticated user.

    Validates JWT token and returns user context with organization info.
    Raises HTTPException if not authenticated.
    """
    settings = get_settings()

    # Skip auth in debug mode if Supabase not configured
    if settings.debug and not settings.supabase_enabled:
        return CurrentUser(
            user_id="00000000-0000-0000-0000-000000000000",
            email="debug@example.com",
            full_name="Debug User",
            org_id="00000000-0000-0000-0000-000000000001",
            org_name="Debug Organization",
            org_role="owner",
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "Authentication required. Include Authorization: Bearer <token> header.",
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        current_user = await auth_service.get_current_user(credentials.credentials)
        return current_user

    except AuthError as e:
        logger.warning(f"Auth failed: {e.code} - {e.message}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> Optional[CurrentUser]:
    """
    Dependency to get current user if authenticated, None otherwise.

    For endpoints that work both with and without authentication.
    """
    settings = get_settings()

    if not credentials:
        if settings.debug and not settings.supabase_enabled:
            return CurrentUser(
                user_id="00000000-0000-0000-0000-000000000000",
                email="debug@example.com",
                full_name="Debug User",
                org_id="00000000-0000-0000-0000-000000000001",
                org_name="Debug Organization",
                org_role="owner",
            )
        return None

    try:
        return await auth_service.get_current_user(credentials.credentials)
    except AuthError:
        return None


def require_org(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """
    Dependency that requires user to belong to an organization.

    Use this for endpoints that require org context for multi-tenancy.
    """
    if not current_user.has_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "NO_ORGANIZATION",
                    "message": "You must belong to an organization to access this resource. Create or join an organization first.",
                }
            },
        )
    return current_user


def require_org_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """
    Dependency that requires user to be an org admin.

    Use for admin-only operations like inviting users, managing settings.
    """
    if not current_user.has_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "NO_ORGANIZATION",
                    "message": "You must belong to an organization to access this resource.",
                }
            },
        )

    if not current_user.is_org_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "ADMIN_REQUIRED",
                    "message": "This operation requires admin privileges.",
                }
            },
        )

    return current_user


def require_org_owner(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """
    Dependency that requires user to be the org owner.

    Use for owner-only operations like deleting org, transferring ownership.
    """
    if not current_user.has_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "NO_ORGANIZATION",
                    "message": "You must belong to an organization to access this resource.",
                }
            },
        )

    if not current_user.is_org_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "OWNER_REQUIRED",
                    "message": "This operation requires owner privileges.",
                }
            },
        )

    return current_user
