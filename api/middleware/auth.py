"""Authentication middleware and utilities."""

import secrets
from datetime import datetime, timedelta
from typing import Optional
import hashlib

# For JWT support (Phase 2)
# from jose import JWTError, jwt


def generate_api_key(prefix: str = "hc") -> str:
    """Generate a new API key."""
    random_bytes = secrets.token_bytes(24)
    key = f"{prefix}_{secrets.token_urlsafe(24)}"
    return key


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash."""
    return secrets.compare_digest(
        hash_api_key(api_key),
        hashed_key
    )


# JWT utilities for Phase 2
class JWTConfig:
    """JWT configuration."""

    SECRET_KEY: str = "change-me-in-production"  # From env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.

    Requires: pip install python-jose[cryptography]
    """
    # Uncomment when JWT is needed
    # to_encode = data.copy()
    # expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    # to_encode.update({"exp": expire})
    # return jwt.encode(to_encode, JWTConfig.SECRET_KEY, algorithm=JWTConfig.ALGORITHM)
    raise NotImplementedError("JWT support not enabled. Use API keys.")


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    # Uncomment when JWT is needed
    # return jwt.decode(token, JWTConfig.SECRET_KEY, algorithms=[JWTConfig.ALGORITHM])
    raise NotImplementedError("JWT support not enabled. Use API keys.")
