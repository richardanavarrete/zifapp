"""
Authentication API Endpoints

User registration, login, and organization management.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from api.supabase.auth_service import AuthError, AuthService
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
async def register(
    request: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Register a new user account.

    Optionally create a new organization or join an existing one via invite code.
    """
    try:
        response = await auth_service.register(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            organization_name=request.organization_name,
            invite_code=request.invite_code,
        )
        return response

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message}},
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Login with email and password."""
    try:
        response = await auth_service.login(
            email=request.email,
            password=request.password,
        )
        return response

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": e.code, "message": e.message}},
        )


@router.post("/logout")
async def logout(
    current_user: CurrentUser = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Logout current user and invalidate session."""
    # Note: With JWT, we can't truly invalidate tokens server-side
    # The client should discard the tokens
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=AuthTokens)
async def refresh_tokens(
    request: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Refresh access token using refresh token."""
    try:
        tokens = await auth_service.refresh_tokens(request.refresh_token)
        return tokens

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": e.code, "message": e.message}},
        )


# =============================================================================
# Password Management
# =============================================================================

@router.post("/password/reset")
async def request_password_reset(
    request: PasswordResetRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Request password reset email."""
    await auth_service.request_password_reset(request.email)
    # Always return success to prevent email enumeration
    return {"message": "If an account exists with this email, a reset link has been sent."}


@router.post("/password/update")
async def update_password(
    request: PasswordUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Update password for authenticated user."""
    try:
        await auth_service.update_password(
            access_token="",  # Token is validated by get_current_user
            new_password=request.password,
        )
        return {"message": "Password updated successfully"}

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message}},
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
    auth_service: AuthService = Depends(get_auth_service),
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
    auth_service: AuthService = Depends(get_auth_service),
):
    """Get the current user's organization."""
    org = await auth_service.get_organization(current_user.org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found"}},
        )
    return org


@router.get("/organizations/{org_id}", response_model=Organization)
async def get_organization(
    org_id: UUID,
    current_user: CurrentUser = Depends(require_org),
    auth_service: AuthService = Depends(get_auth_service),
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
    auth_service: AuthService = Depends(get_auth_service),
):
    """List members of the current organization."""
    client = auth_service.client

    result = client.table("organization_members").select(
        "*, user_profiles(email, full_name)"
    ).eq("org_id", str(current_user.org_id)).execute()

    members = []
    for row in result.data or []:
        profile = row.get("user_profiles", {})
        members.append(OrganizationMember(
            org_id=UUID(row["org_id"]),
            user_id=UUID(row["user_id"]),
            role=OrganizationRole(row["role"]),
            email=profile.get("email") if profile else None,
            full_name=profile.get("full_name") if profile else None,
            joined_at=row["joined_at"],
            invited_by=UUID(row["invited_by"]) if row.get("invited_by") else None,
        ))

    return members


@router.post("/organizations/current/invite")
async def invite_member(
    email: str,
    role: OrganizationRole = OrganizationRole.MEMBER,
    current_user: CurrentUser = Depends(require_org_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Invite a user to join the organization.

    Only admins and owners can invite new members.
    """
    import secrets
    from datetime import datetime, timedelta

    client = auth_service.client

    # Create invite
    invite_code = secrets.token_urlsafe(16)
    expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()

    invite_data = {
        "org_id": str(current_user.org_id),
        "email": email,
        "role": role.value,
        "code": invite_code,
        "expires_at": expires_at,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": str(current_user.user_id),
        "accepted": False,
    }

    client.table("organization_invites").insert(invite_data).execute()

    # In production, send email with invite link
    # For now, just return the code
    return {
        "message": f"Invitation sent to {email}",
        "invite_code": invite_code,
        "expires_at": expires_at,
    }


@router.delete("/organizations/current/members/{user_id}")
async def remove_member(
    user_id: UUID,
    current_user: CurrentUser = Depends(require_org_admin),
    auth_service: AuthService = Depends(get_auth_service),
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

    client = auth_service.client

    # Get member's role
    result = client.table("organization_members").select("role").eq("org_id", str(current_user.org_id)).eq("user_id", str(user_id)).single().execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "MEMBER_NOT_FOUND", "message": "Member not found"}},
        )

    member_role = OrganizationRole(result.data["role"])

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

    # Remove member
    client.table("organization_members").delete().eq("org_id", str(current_user.org_id)).eq("user_id", str(user_id)).execute()

    return {"message": "Member removed successfully"}


@router.post("/organizations/current/leave")
async def leave_organization(
    current_user: CurrentUser = Depends(require_org),
    auth_service: AuthService = Depends(get_auth_service),
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

    client = auth_service.client
    client.table("organization_members").delete().eq("org_id", str(current_user.org_id)).eq("user_id", str(current_user.user_id)).execute()

    return {"message": "Left organization successfully"}
