"""
Authentication API Endpoints

User registration, login, and organization management.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.auth.errors import AuthError
from api.config import get_settings
from api.middleware.rate_limit import limiter
from api.supabase.middleware import (
    get_auth_service,
    get_current_user,
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
    PasswordResetRequest,
    PasswordUpdateRequest,
    RefreshRequest,
    User,
    UserCreate,
    UserProfile,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# =============================================================================
# Registration & Login
# =============================================================================

@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().rate_limit_login)
async def register(
    request: Request,
    user_request: UserCreate,
    auth_service = Depends(get_auth_service),
):
    """
    Register a new user account.

    Optionally create a new organization or join an existing one via invite code.
    """
    try:
        response = await auth_service.register(
            email=user_request.email,
            password=user_request.password,
            full_name=user_request.full_name,
            organization_name=user_request.organization_name,
            invite_code=user_request.invite_code,
        )
        return response

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message}},
        )
    except Exception as e:
        logger.error(f"Unexpected error during registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "REGISTRATION_FAILED", "message": "An unexpected error occurred during registration."}},
        )


@router.post("/login", response_model=LoginResponse)
@limiter.limit(lambda: get_settings().rate_limit_login)
async def login(
    request: Request,
    login_request: LoginRequest,
    auth_service = Depends(get_auth_service),
):
    """Login with email and password."""
    try:
        response = await auth_service.login(
            email=login_request.email,
            password=login_request.password,
        )
        return response

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": e.code, "message": e.message}},
        )
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LOGIN_FAILED", "message": "An unexpected error occurred during login."}},
        )


@router.post("/logout")
async def logout(
    current_user: CurrentUser = Depends(get_current_user),
    auth_service = Depends(get_auth_service),
):
    """Logout current user and invalidate session."""
    # Note: With JWT, we can't truly invalidate tokens server-side
    # The client should discard the tokens
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=AuthTokens)
@limiter.limit(lambda: get_settings().rate_limit_auth_general)
async def refresh_tokens(
    request: Request,
    refresh_request: RefreshRequest,
    auth_service = Depends(get_auth_service),
):
    """Refresh access token using refresh token."""
    try:
        tokens = await auth_service.refresh_tokens(refresh_request.refresh_token)
        return tokens

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": e.code, "message": e.message}},
        )
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "REFRESH_FAILED", "message": "An unexpected error occurred during token refresh."}},
        )


# =============================================================================
# Password Management
# =============================================================================

@router.post("/password/reset")
@limiter.limit(lambda: get_settings().rate_limit_login)
async def request_password_reset(
    request: Request,
    reset_request: PasswordResetRequest,
    auth_service = Depends(get_auth_service),
):
    """Request password reset email."""
    try:
        await auth_service.request_password_reset(reset_request.email)
        # Always return success to prevent email enumeration
        return {"message": "If an account exists with this email, a reset link has been sent."}
    except Exception as e:
        logger.error(f"Unexpected error during password reset: {e}")
        # Still return success to prevent email enumeration
        return {"message": "If an account exists with this email, a reset link has been sent."}


@router.post("/password/update")
@limiter.limit(lambda: get_settings().rate_limit_login)
async def update_password(
    request: Request,
    update_request: PasswordUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    auth_service = Depends(get_auth_service),
):
    """Update password for authenticated user."""
    try:
        await auth_service.update_password(
            access_token="",  # Token is validated by get_current_user
            new_password=update_request.password,
        )
        return {"message": "Password updated successfully"}

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message}},
        )
    except Exception as e:
        logger.error(f"Unexpected error during password update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "PASSWORD_UPDATE_FAILED", "message": "An unexpected error occurred."}},
        )


# =============================================================================
# Current User
# =============================================================================

@router.get("/me", response_model=CurrentUser)
async def get_me(current_user: CurrentUser = Depends(get_current_user)):
    """Get current authenticated user with organization context."""
    return current_user


# =============================================================================
# Organization Management
# =============================================================================

@router.post("/organizations", response_model=Organization, status_code=status.HTTP_201_CREATED)
async def create_organization(
    request: OrganizationCreate,
    current_user: CurrentUser = Depends(get_current_user),
    auth_service = Depends(get_auth_service),
):
    """
    Create a new organization.

    The current user becomes the owner.
    """
    if current_user.has_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "ALREADY_IN_ORG",
                    "message": "You already belong to an organization. Leave your current org first.",
                }
            },
        )

    try:
        org = await auth_service.create_organization(
            user_id=current_user.user_id,
            name=request.name,
            slug=request.slug,
        )
        return org

    except Exception as e:
        logger.error(f"Failed to create organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "ORG_CREATE_FAILED", "message": str(e)}},
        )


@router.get("/organizations/current", response_model=Organization)
async def get_current_organization(
    current_user: CurrentUser = Depends(require_org),
    auth_service = Depends(get_auth_service),
):
    """Get the current user's organization."""
    try:
        org = await auth_service.get_organization(current_user.org_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found"}},
            )
        return org
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}},
        )


@router.get("/organizations/{org_id}", response_model=Organization)
async def get_organization(
    org_id: UUID,
    current_user: CurrentUser = Depends(require_org),
    auth_service = Depends(get_auth_service),
):
    """Get organization by ID (must be a member)."""
    if current_user.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "NOT_A_MEMBER", "message": "You are not a member of this organization"}},
        )

    org = await auth_service.get_organization(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found"}},
        )
    return org


@router.get("/organizations/current/members", response_model=List[OrganizationMember])
async def list_organization_members(
    current_user: CurrentUser = Depends(require_org),
    auth_service = Depends(get_auth_service),
):
    """List members of the current organization."""
    try:
        return await auth_service.list_org_members(current_user.org_id)
    except Exception as e:
        logger.error(f"Unexpected error listing org members: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}},
        )


@router.post("/organizations/current/invite")
async def invite_member(
    email: str,
    role: OrganizationRole = OrganizationRole.MEMBER,
    current_user: CurrentUser = Depends(require_org_admin),
    auth_service = Depends(get_auth_service),
):
    """
    Invite a user to join the organization.

    Only admins and owners can invite new members.
    """
    try:
        return await auth_service.create_invite(
            org_id=current_user.org_id,
            email=email,
            role=role,
            created_by=current_user.user_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating invite: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}},
        )


@router.delete("/organizations/current/members/{user_id}")
async def remove_member(
    user_id: UUID,
    current_user: CurrentUser = Depends(require_org_admin),
    auth_service = Depends(get_auth_service),
):
    """
    Remove a member from the organization.

    Admins can remove members. Only owners can remove admins.
    """
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "CANNOT_REMOVE_SELF", "message": "Use leave endpoint to leave the organization"}},
        )

    member_role = await auth_service.get_member_role(current_user.org_id, user_id)

    if not member_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "MEMBER_NOT_FOUND", "message": "Member not found"}},
        )

    # Only owner can remove admins
    if member_role == OrganizationRole.ADMIN and not current_user.is_org_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "CANNOT_REMOVE_ADMIN", "message": "Only the owner can remove admins"}},
        )

    # Cannot remove owner
    if member_role == OrganizationRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "CANNOT_REMOVE_OWNER", "message": "Cannot remove the organization owner"}},
        )

    await auth_service.remove_member(current_user.org_id, user_id)
    return {"message": "Member removed successfully"}


@router.post("/organizations/current/leave")
async def leave_organization(
    current_user: CurrentUser = Depends(require_org),
    auth_service = Depends(get_auth_service),
):
    """Leave the current organization."""
    if current_user.is_org_owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "OWNER_CANNOT_LEAVE",
                    "message": "Organization owner cannot leave. Transfer ownership or delete the organization.",
                }
            },
        )

    await auth_service.leave_organization(current_user.org_id, current_user.user_id)
    return {"message": "Left organization successfully"}
