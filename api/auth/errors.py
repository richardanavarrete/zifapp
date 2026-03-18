"""Shared authentication errors."""


class AuthError(Exception):
    """Authentication error."""

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)
