"""
config.py — Application configuration via Pydantic Settings
============================================================

WHY Pydantic Settings?
----------------------
Instead of scattered os.getenv() calls throughout the codebase, we define
ALL configuration in one typed class. Pydantic validates types at startup
(e.g. ensures DATABASE_URL is actually a string, SECRET_KEY exists, etc.)
and raises a clear error immediately if anything is misconfigured — rather
than a mysterious crash at runtime.

Loading order: environment variables > .env file > default values.
This means Docker/Railway env vars always override .env — perfect for
having different configs per environment without changing code.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://pesa:pesa@localhost:5432/pesadb"
    # The +asyncpg dialect prefix routes SQLAlchemy to use the asyncpg driver.

    # JWT
    secret_key: str = "CHANGE_THIS_IN_PRODUCTION_USE_openssl_rand_hex_32"
    algorithm: str = "HS256"
    # HS256 = HMAC-SHA256: symmetric signing. Both signing and verification
    # use the same secret_key. Simpler than RS256 (asymmetric) for a single
    # service with no external JWT consumers.
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # App
    debug: bool = False
    app_name: str = "Pesa API"
    api_v1_prefix: str = "/api/v1"
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    # C++ library path (relative to the running process)
    lib_path: str = "./cpp/libfinance.so"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # case_sensitive=False: DATABASE_URL and database_url both work.
    )


# Module-level singleton — import this everywhere rather than
# re-instantiating Settings() in each file (avoids repeated .env reads).
settings = Settings()
