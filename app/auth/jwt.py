"""
JWT token creation and decoding.

Algorithm : HS256
Claims    : sub (user UUID as str), role, iat, exp
TTL       : ACCESS_TOKEN_EXPIRE_MINUTES (from settings, default 60 min)
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.config import settings


def create_access_token(subject: str, role: str) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: The user's UUID string (stored in the 'sub' claim).
        role:    The user's role string ('organizer' or 'customer').

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Returns:
        The decoded payload dict.

    Raises:
        JWTError: If the token is invalid, expired, or tampered.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
