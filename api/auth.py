"""
auth.py — JWT Authentication Utilities
=======================================

This module contains:
  1. Password hashing (bcrypt directly — no passlib)
  2. JWT token creation and verification (python-jose)
  3. FastAPI dependency: get_current_user (used in protected routes)

The flow:
  Register  → hash password → store in DB
  Login     → verify password → issue JWT
  Protected route → client sends JWT in Authorization header
                  → we decode + verify → load user from DB
                  → inject as dependency into route handler

WHY JWT (not sessions)?
-----------------------
Sessions store state on the server. JWT stores state in the token itself
(stateless). For an API with multiple instances / horizontal scaling, there's
no shared session store needed. The trade-off: you can't invalidate JWTs
before expiry without a blocklist — acceptable for most use cases.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
# OAuth2PasswordBearer:
#   - Tells FastAPI that this route expects a Bearer token in the
#     Authorization header: "Authorization: Bearer <token>"
#   - tokenUrl points to the login endpoint for Swagger UI auto-login.
#   - It does NOT do validation itself — just extracts the token string.

from jose import JWTError, jwt
# python-jose: pure-Python JWT implementation.
# jwt.encode() / jwt.decode() with HMAC-SHA256 (HS256).

import bcrypt
# Using bcrypt directly rather than via passlib.
# passlib 1.7.x is incompatible with bcrypt 4.x: passlib's detect_wrap_bug()
# internally hashes a 73-byte test password, but bcrypt 4.0+ strictly enforces
# the 72-byte limit and raises ValueError. Direct bcrypt usage avoids this entirely.

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.config import settings
from api.database import get_db
from api import models, schemas


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt. NEVER store plain text.

    bcrypt.hashpw requires bytes — we encode to UTF-8 first.
    gensalt(rounds=12): work factor of 2^12 iterations (~250ms on modern hardware).
    12 is the industry-standard default — slow enough to resist brute-force,
    fast enough that real users don't notice.
    We decode back to str for storage in the TEXT column.
    """
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Compare a plain-text password against a stored bcrypt hash.
    bcrypt.checkpw uses constant-time comparison — not vulnerable to timing attacks.
    Both arguments must be bytes, so we encode both.
    """
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Encode a JWT token.

    The payload ('claims') contains:
      sub: subject (user ID as string)
      exp: expiry timestamp (Unix epoch)
      iat: issued-at timestamp
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> schemas.TokenData:
    """
    Decode and validate a JWT token.
    Raises HTTP 401 on any failure (expired, tampered, wrong key, etc.)

    WHY one generic exception for all JWT errors?
    Security best practice: don't tell the client WHY the token failed.
    "Token expired" vs "Invalid signature" gives attackers useful information.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
        # The WWW-Authenticate header is required by RFC 6750 for Bearer token errors.
    )
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return schemas.TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception


# ---------------------------------------------------------------------------
# FastAPI dependency: get_current_user
# ---------------------------------------------------------------------------
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> models.User:
    """
    FastAPI dependency that:
    1. Extracts the Bearer token from the Authorization header
    2. Decodes and validates the JWT
    3. Loads the user from the database
    4. Returns the User ORM object

    Usage in routes:
        @router.get("/me")
        async def me(user: User = Depends(get_current_user)):
            return user

    If anything fails (bad token, user deleted, inactive), raises HTTP 401/403.
    FastAPI's dependency injection handles calling this automatically.
    """
    token_data = decode_token(token)

    result = await db.execute(
        select(models.User).where(models.User.id == token_data.user_id)
    )
    user = result.scalar_one_or_none()
    # scalar_one_or_none(): returns the single row or None (no exception).
    # Contrast with scalar_one() which raises if row doesn't exist.

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return user


async def get_current_active_user(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    """Alias dependency for routes that want explicit 'active user' semantics."""
    return current_user
