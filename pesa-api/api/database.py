"""
database.py — Async database engine and session factory
========================================================

WHY async SQLAlchemy?
---------------------
FastAPI is built on asyncio. If database calls were synchronous (blocking),
every DB query would freeze the entire event loop — no other requests could
be processed during that time. With async SQLAlchemy + asyncpg, the event loop
yields control while waiting for Postgres, letting other requests run concurrently.

This is especially important for an API under load: 100 concurrent users
making DB calls would be handled with N threads (sync) vs. 1 thread + coroutines
(async). The async approach uses far less memory and handles more concurrency.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from api.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# create_async_engine is the async equivalent of create_engine.
# The URL must use the "postgresql+asyncpg" dialect prefix — this tells
# SQLAlchemy to use asyncpg as the driver instead of psycopg2.
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,          # Log SQL statements in debug mode
    pool_size=10,                  # Max persistent connections in the pool
    max_overflow=20,               # Extra connections allowed when pool is full
    pool_pre_ping=True,            # Test connections before using them (handles DB restarts)
    # pool_pre_ping sends a lightweight "SELECT 1" before each checkout.
    # Without this, stale connections after a DB restart would cause errors.
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
# async_sessionmaker creates AsyncSession instances.
# expire_on_commit=False is important for async use:
#   Normally SQLAlchemy expires all ORM attributes after commit() so they
#   are reloaded from DB on next access. In async code, that "lazy reload"
#   would trigger an I/O operation outside an async context — causing errors.
#   expire_on_commit=False keeps attribute values in memory after commit.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
    # autoflush=False: don't send pending SQL automatically before queries.
    # We control flushing explicitly, which avoids surprising DB writes.
)


# ---------------------------------------------------------------------------
# Base class for all ORM models
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """All ORM model classes inherit from this Base.

    WHY DeclarativeBase (SQLAlchemy 2.0 style)?
    The old Base = declarative_base() still works but is considered legacy.
    DeclarativeBase is the modern approach: it supports Python type hints
    and integrates cleanly with mypy / pyright.
    """
    pass


# ---------------------------------------------------------------------------
# Dependency for FastAPI route handlers
# ---------------------------------------------------------------------------
async def get_db() -> AsyncSession:
    """
    FastAPI dependency that provides a database session for each request.

    Usage in a route:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...

    WHY a generator (yield)?
    FastAPI runs the code before `yield` as setup, and code after `yield` as
    teardown (even if an exception occurred). This guarantees the session is
    always closed — no connection leaks, even on errors.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
            # Auto-commit on successful request completion.
            # If the route raises an exception, we fall into `except` and rollback.
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
