"""
Supabase Auth Service

Handles user authentication, registration, and JWT validation.
"""

import logging
import re
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID, uuid4

import jwt
from gotrue.errors import AuthApiError
from pydantic import EmailStr

from api.config import get_settings
from api.supabase.client import get_supabase_admin_client, get_supabase_client
from api.supabase.models import (
    AuthTokens,
    CurrentUser,
    LoginResponse,
    Organization,
    OrganizationRole,
    User,
    UserProfile,
)

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Authentication error."""

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class AuthService:
    """
    Supabase authentication service.

    Handles:
    - User registration and login
    - JWT token validation
    - Organization management
    """

    def __init__(self):
        self.client = get_supabase_client()
        self._admin_client = None

    @property
    def admin_client(self):
        """Lazy-load admin client."""
        if self._admin_client is None:
            self._admin_client = get_supabase_admin_client()
        return self._admin_client

    # =========================================================================
    # User Registration
    # =========================================================================

    async def register(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        organization_name: Optional[str] = None,
        invite_code: Optional[str] = None,
    ) -> LoginResponse:
        """
        Register a new user.

        Optionally creates a new organization or joins an existing one via invite.
        """
        try:
            # Register with Supabase Auth
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "full_name": full_name,
                    }
                }
            })

            if not response.user:
                raise AuthError("Registration failed", "REGISTRATION_FAILED")

            user = self._map_supabase_user(response.user)

            # Create user profile in our database
            profile = await self._create_user_profile(
                user_id=user.id,
                email=email,
                full_name=full_name,
            )

            # Handle organization
            if organization_name:
                # Create new organization
                org = await self._create_organization(
                    name=organization_name,
                    owner_id=user.id,
                )
                profile = await self._add_user_to_org(
                    user_id=user.id,
                    org_id=org.id,
                    role=OrganizationRole.OWNER,
                )
            elif invite_code:
                # Join existing organization via invite
                profile = await self._accept_invite(user.id, invite_code)

            tokens = AuthTokens(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                token_type="bearer",
                expires_in=response.session.expires_in or 3600,
                expires_at=response.session.expires_at,
            )

            return LoginResponse(
                user=user,
                profile=profile,
                tokens=tokens,
            )

        except AuthApiError as e:
            logger.error(f"Registration error: {e}")
            if "already registered" in str(e).lower():
                raise AuthError("Email already registered", "EMAIL_EXISTS")
            raise AuthError(str(e), "REGISTRATION_FAILED")

    # =========================================================================
    # Login / Logout
    # =========================================================================

    async def login(self, email: str, password: str) -> LoginResponse:
        """Login with email and password."""
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })

            if not response.user or not response.session:
                raise AuthError("Invalid credentials", "INVALID_CREDENTIALS")

            user = self._map_supabase_user(response.user)

            # Get user profile with org info
            profile = await self._get_user_profile(user.id)
            if not profile:
                # Create profile if doesn't exist (legacy user)
                profile = await self._create_user_profile(
                    user_id=user.id,
                    email=email,
                    full_name=user.full_name,
                )

            tokens = AuthTokens(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                token_type="bearer",
                expires_in=response.session.expires_in or 3600,
                expires_at=response.session.expires_at,
            )

            return LoginResponse(
                user=user,
                profile=profile,
                tokens=tokens,
            )

        except AuthApiError as e:
            logger.error(f"Login error: {e}")
            raise AuthError("Invalid credentials", "INVALID_CREDENTIALS")

    async def logout(self, access_token: str) -> bool:
        """Logout user and invalidate session."""
        try:
            self.client.auth.sign_out()
            return True
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False

    async def refresh_tokens(self, refresh_token: str) -> AuthTokens:
        """Refresh access token using refresh token."""
        try:
            response = self.client.auth.refresh_session(refresh_token)

            if not response.session:
                raise AuthError("Invalid refresh token", "INVALID_REFRESH_TOKEN")

            return AuthTokens(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                token_type="bearer",
                expires_in=response.session.expires_in or 3600,
                expires_at=response.session.expires_at,
            )

        except AuthApiError as e:
            logger.error(f"Token refresh error: {e}")
            raise AuthError("Invalid refresh token", "INVALID_REFRESH_TOKEN")

    # =========================================================================
    # JWT Validation
    # =========================================================================

    def validate_token(self, token: str) -> Tuple[UUID, str]:
        """
        Validate a JWT token and extract user info.

        Returns: (user_id, email)
        Raises: AuthError if token is invalid
        """
        settings = get_settings()

        if not settings.supabase_jwt_secret:
            # Fall back to verifying with Supabase API
            return self._validate_token_via_api(token)

        try:
            # Decode and verify JWT
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )

            user_id = UUID(payload.get("sub"))
            email = payload.get("email", "")

            # Check expiration (jwt.decode already does this, but be explicit)
            exp = payload.get("exp")
            if exp and datetime.utcnow().timestamp() > exp:
                raise AuthError("Token expired", "TOKEN_EXPIRED")

            return user_id, email

        except jwt.ExpiredSignatureError:
            raise AuthError("Token expired", "TOKEN_EXPIRED")
        except jwt.InvalidTokenError as e:
            logger.error(f"JWT validation error: {e}")
            raise AuthError("Invalid token", "INVALID_TOKEN")

    def _validate_token_via_api(self, token: str) -> Tuple[UUID, str]:
        """Validate token by calling Supabase API."""
        try:
            response = self.client.auth.get_user(token)

            if not response.user:
                raise AuthError("Invalid token", "INVALID_TOKEN")

            return UUID(response.user.id), response.user.email

        except AuthApiError as e:
            logger.error(f"Token validation error: {e}")
            raise AuthError("Invalid token", "INVALID_TOKEN")

    async def get_current_user(self, token: str) -> CurrentUser:
        """
        Get full current user context from token.

        Includes organization membership info for multi-tenancy.
        """
        user_id, email = self.validate_token(token)

        # Get profile with org info
        profile = await self._get_user_profile(user_id)

        return CurrentUser(
            user_id=user_id,
            email=email,
            full_name=profile.full_name if profile else None,
            org_id=profile.org_id if profile else None,
            org_name=profile.org_name if profile else None,
            org_role=profile.org_role if profile else None,
        )

    # =========================================================================
    # Password Management
    # =========================================================================

    async def request_password_reset(self, email: str) -> bool:
        """Send password reset email."""
        try:
            self.client.auth.reset_password_email(email)
            return True
        except AuthApiError as e:
            logger.error(f"Password reset error: {e}")
            # Don't reveal if email exists
            return True

    async def update_password(self, access_token: str, new_password: str) -> bool:
        """Update user password."""
        try:
            self.client.auth.update_user({"password": new_password})
            return True
        except AuthApiError as e:
            logger.error(f"Password update error: {e}")
            raise AuthError("Password update failed", "PASSWORD_UPDATE_FAILED")

    # =========================================================================
    # Organization Management
    # =========================================================================

    async def create_organization(
        self,
        user_id: UUID,
        name: str,
        slug: Optional[str] = None,
    ) -> Organization:
        """Create a new organization with user as owner."""
        org = await self._create_organization(name, user_id, slug)
        await self._add_user_to_org(user_id, org.id, OrganizationRole.OWNER)
        return org

    async def get_organization(self, org_id: UUID) -> Optional[Organization]:
        """Get organization by ID."""
        result = self.client.table("organizations").select("*").eq("id", str(org_id)).single().execute()

        if not result.data:
            return None

        return Organization(
            id=UUID(result.data["id"]),
            name=result.data["name"],
            slug=result.data["slug"],
            plan=result.data.get("plan", "free"),
            created_at=datetime.fromisoformat(result.data["created_at"]),
            updated_at=datetime.fromisoformat(result.data["updated_at"]) if result.data.get("updated_at") else None,
            owner_id=UUID(result.data["owner_id"]),
        )

    async def get_user_organization(self, user_id: UUID) -> Optional[Organization]:
        """Get the organization a user belongs to."""
        # Get membership
        result = self.client.table("organization_members").select("org_id").eq("user_id", str(user_id)).single().execute()

        if not result.data:
            return None

        return await self.get_organization(UUID(result.data["org_id"]))

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _map_supabase_user(self, supabase_user) -> User:
        """Map Supabase user object to our User model."""
        user_metadata = supabase_user.user_metadata or {}

        return User(
            id=UUID(supabase_user.id),
            email=supabase_user.email,
            email_confirmed_at=datetime.fromisoformat(supabase_user.email_confirmed_at.replace("Z", "+00:00")) if supabase_user.email_confirmed_at else None,
            created_at=datetime.fromisoformat(supabase_user.created_at.replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(supabase_user.updated_at.replace("Z", "+00:00")) if supabase_user.updated_at else None,
            full_name=user_metadata.get("full_name"),
            avatar_url=user_metadata.get("avatar_url"),
        )

    async def _create_user_profile(
        self,
        user_id: UUID,
        email: str,
        full_name: Optional[str] = None,
    ) -> UserProfile:
        """Create user profile in database."""
        now = datetime.utcnow().isoformat()

        data = {
            "user_id": str(user_id),
            "email": email,
            "full_name": full_name,
            "created_at": now,
            "updated_at": now,
        }

        self.client.table("user_profiles").insert(data).execute()

        return UserProfile(
            user_id=user_id,
            email=email,
            full_name=full_name,
            created_at=datetime.utcnow(),
        )

    async def _get_user_profile(self, user_id: UUID) -> Optional[UserProfile]:
        """Get user profile with organization info."""
        # Join user_profiles with organization_members and organizations
        result = self.client.table("user_profiles").select(
            "*, organization_members(org_id, role), organizations(id, name)"
        ).eq("user_id", str(user_id)).single().execute()

        if not result.data:
            return None

        data = result.data
        org_member = data.get("organization_members")
        org = data.get("organizations")

        return UserProfile(
            user_id=UUID(data["user_id"]),
            email=data["email"],
            full_name=data.get("full_name"),
            avatar_url=data.get("avatar_url"),
            org_id=UUID(org_member["org_id"]) if org_member else None,
            org_name=org["name"] if org else None,
            org_role=OrganizationRole(org_member["role"]) if org_member else None,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )

    async def _create_organization(
        self,
        name: str,
        owner_id: UUID,
        slug: Optional[str] = None,
    ) -> Organization:
        """Create organization in database."""
        if not slug:
            # Generate slug from name
            slug = self._generate_slug(name)

        now = datetime.utcnow().isoformat()
        org_id = uuid4()

        data = {
            "id": str(org_id),
            "name": name,
            "slug": slug,
            "owner_id": str(owner_id),
            "plan": "free",
            "created_at": now,
            "updated_at": now,
        }

        self.client.table("organizations").insert(data).execute()

        return Organization(
            id=org_id,
            name=name,
            slug=slug,
            plan="free",
            created_at=datetime.utcnow(),
            owner_id=owner_id,
        )

    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from name."""
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s_-]+", "-", slug)
        slug = slug.strip("-")

        # Add random suffix for uniqueness
        suffix = uuid4().hex[:6]
        return f"{slug}-{suffix}"

    async def _add_user_to_org(
        self,
        user_id: UUID,
        org_id: UUID,
        role: OrganizationRole,
    ) -> UserProfile:
        """Add user to organization."""
        now = datetime.utcnow().isoformat()

        data = {
            "org_id": str(org_id),
            "user_id": str(user_id),
            "role": role.value,
            "joined_at": now,
        }

        self.client.table("organization_members").insert(data).execute()

        # Return updated profile
        return await self._get_user_profile(user_id)

    async def _accept_invite(self, user_id: UUID, invite_code: str) -> UserProfile:
        """Accept organization invite."""
        # Get invite
        result = self.client.table("organization_invites").select("*").eq("code", invite_code).eq("accepted", False).single().execute()

        if not result.data:
            raise AuthError("Invalid or expired invite code", "INVALID_INVITE")

        invite = result.data

        # Check expiration
        expires_at = datetime.fromisoformat(invite["expires_at"])
        if datetime.utcnow() > expires_at:
            raise AuthError("Invite code expired", "INVITE_EXPIRED")

        # Add user to org
        profile = await self._add_user_to_org(
            user_id=user_id,
            org_id=UUID(invite["org_id"]),
            role=OrganizationRole(invite["role"]),
        )

        # Mark invite as accepted
        self.client.table("organization_invites").update({"accepted": True}).eq("id", invite["id"]).execute()

        return profile
