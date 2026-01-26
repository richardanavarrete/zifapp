"""
Supabase Auth and Multi-tenancy Models

User and Organization models for multi-tenant inventory management.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class OrganizationRole(str, Enum):
    """User roles within an organization."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class UserCreate(BaseModel):
    """Request model for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    organization_name: Optional[str] = Field(
        default=None,
        description="Create a new organization during registration"
    )
    invite_code: Optional[str] = Field(
        default=None,
        description="Join existing organization via invite"
    )


class User(BaseModel):
    """User model from Supabase Auth."""
    id: UUID
    email: EmailStr
    email_confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # App metadata
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserProfile(BaseModel):
    """Extended user profile stored in our database."""
    user_id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    # Organization membership
    org_id: Optional[UUID] = None
    org_name: Optional[str] = None
    org_role: Optional[OrganizationRole] = None

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None


class OrganizationCreate(BaseModel):
    """Request model for creating an organization."""
    name: str = Field(..., min_length=2, max_length=100)
    slug: Optional[str] = Field(
        default=None,
        description="URL-friendly identifier (auto-generated if not provided)"
    )


class Organization(BaseModel):
    """Organization (tenant) model."""
    id: UUID
    name: str
    slug: str = Field(..., description="URL-friendly unique identifier")

    # Subscription/billing (for future use)
    plan: str = Field(default="free", description="Subscription plan")

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Owner info
    owner_id: UUID


class OrganizationMember(BaseModel):
    """Organization membership model."""
    org_id: UUID
    user_id: UUID
    role: OrganizationRole

    # User info (joined)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None

    # Timestamps
    joined_at: datetime
    invited_by: Optional[UUID] = None


class OrganizationInvite(BaseModel):
    """Invitation to join an organization."""
    id: UUID
    org_id: UUID
    email: EmailStr
    role: OrganizationRole = OrganizationRole.MEMBER

    # Invite code for URL
    code: str = Field(..., description="Unique invite code")

    # Status
    accepted: bool = False
    expires_at: datetime
    created_at: datetime
    created_by: UUID


# =============================================================================
# Auth Response Models
# =============================================================================

class AuthTokens(BaseModel):
    """Authentication tokens returned by Supabase."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiry in seconds")
    expires_at: Optional[int] = Field(None, description="Unix timestamp of expiry")


class LoginRequest(BaseModel):
    """Login request model."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response with user and tokens."""
    user: User
    profile: UserProfile
    tokens: AuthTokens


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Password reset request."""
    email: EmailStr


class PasswordUpdateRequest(BaseModel):
    """Password update request."""
    password: str = Field(..., min_length=8)


# =============================================================================
# Current User Context
# =============================================================================

class CurrentUser(BaseModel):
    """
    Current authenticated user context.

    Injected into endpoints via dependency injection.
    Contains user info and organization context for multi-tenancy.
    """
    user_id: UUID
    email: EmailStr
    full_name: Optional[str] = None

    # Organization context (required for data access)
    org_id: Optional[UUID] = None
    org_name: Optional[str] = None
    org_role: Optional[OrganizationRole] = None

    @property
    def is_org_admin(self) -> bool:
        """Check if user has admin rights in their org."""
        return self.org_role in (OrganizationRole.OWNER, OrganizationRole.ADMIN)

    @property
    def is_org_owner(self) -> bool:
        """Check if user is the org owner."""
        return self.org_role == OrganizationRole.OWNER

    @property
    def has_org(self) -> bool:
        """Check if user belongs to an organization."""
        return self.org_id is not None
