"""
routers/auth.py — Authentication Endpoints
==========================================

Routes:
  POST /api/v1/auth/register  → create account
  POST /api/v1/auth/login     → return JWT
  GET  /api/v1/auth/me        → return current user profile
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api import models, schemas
from api.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_active_user,
)
from api.database import get_db

# APIRouter is a "mini app" — a group of related routes.
# We mount it in main.py with a prefix, so all routes here get /api/v1/auth/...
# WHY use routers?
#   Keeps main.py clean. Each domain (auth, transactions, budgets) lives in
#   its own file. Easy to enable/disable features.
router = APIRouter(prefix="/auth", tags=["Authentication"])
# tags=["Authentication"] groups these endpoints in the Swagger UI docs.


@router.post(
    "/register",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    user_in: schemas.UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new user account.

    WHY async def (not def)?
    The DB call (await db.execute) is I/O. Using async def + await lets the
    event loop handle other requests while waiting for Postgres. If we used
    sync def, this route would block the entire server during DB I/O.

    FastAPI auto-deserialises the request body into UserCreate (Pydantic validates it),
    and serialises the return value into UserResponse (filtering out hashed_password).
    """
    # Check for existing user
    existing = await db.execute(
        select(models.User).where(models.User.email == user_in.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = models.User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
    )
    db.add(user)
    await db.flush()
    # flush() sends the INSERT to Postgres but doesn't COMMIT yet.
    # The session commits in get_db (after yield). This lets us do
    # multiple operations and roll back all of them together on error.

    return user


@router.post(
    "/login",
    response_model=schemas.Token,
    summary="Login and receive a JWT token",
)
async def login(
    login_data: schemas.LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate and return a Bearer token.

    Security note: we use the SAME error message for "user not found" and
    "wrong password" — this prevents user enumeration attacks where an
    attacker probes which emails are registered.
    """
    result = await db.execute(
        select(models.User).where(models.User.email == login_data.email)
    )
    user = result.scalar_one_or_none()

    # Deliberate: same message for both failure modes
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise auth_error

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    token = create_access_token(data={"sub": str(user.id)})
    return schemas.Token(access_token=token)


@router.get(
    "/me",
    response_model=schemas.UserResponse,
    summary="Get current user profile",
)
async def get_me(
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Protected route — requires a valid JWT in the Authorization header.

    Depends(get_current_active_user) is the guard:
      - FastAPI calls get_current_active_user before this function
      - If token is invalid/expired, get_current_active_user raises HTTP 401
        and this function never runs
      - If valid, current_user is the loaded User ORM object

    The route itself is trivially simple — auth complexity lives in the dependency.
    """
    return current_user
