"""
main.py — FastAPI Application Entry Point
==========================================

This is where the app is assembled. Think of it as the "wiring" file:
  - Creates the FastAPI instance
  - Registers routers (each domain's endpoints)
  - Attaches middleware (CORS, logging)
  - Defines startup/shutdown lifecycle events
  - Exposes /health and /api/v1/docs

WHY FastAPI over Flask/Django?
-------------------------------
  Flask:   sync by default, needs extensions for everything
  Django:  batteries included but heavy; ORM not async-native
  FastAPI: async-first, automatic OpenAPI docs, Pydantic validation built-in,
           ~3x faster than Flask in benchmarks, modern Python (type hints)
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api.config import settings
from api.database import engine, Base, get_db
from api.routers import auth, transactions, budgets, analytics
from api import schemas

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — replaces the deprecated @app.on_event("startup/shutdown")
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    WHY lifespan context manager?
    FastAPI 0.93+ recommends this over @app.on_event decorators.
    Code before `yield` runs at startup; code after runs at shutdown.
    Using asynccontextmanager gives us proper async setup/teardown.
    """
    # --- Startup ---
    logger.info("Starting %s ...", settings.app_name)

    # Create tables if they don't exist (dev convenience).
    # In production, use proper migrations (Alembic / the SQL files in sql/).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified ✅")

    yield  # ← app is running here

    # --- Shutdown ---
    await engine.dispose()
    # dispose() closes all connections in the pool cleanly.
    # Without this, you may get "event loop closed" errors on shutdown.
    logger.info("Database connections closed. Goodbye 👋")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    description=(
        "**Pesa API** — Personal Finance Tracking REST API\n\n"
        "Features:\n"
        "- JWT authentication\n"
        "- Transaction management (income & expenses)\n"
        "- Budget tracking with overage alerts\n"
        "- Analytics powered by a C++ finance engine\n\n"
        "Use the **Authorize** button (🔒) to enter your Bearer token."
    ),
    version="1.0.0",
    docs_url="/api/v1/docs",      # Swagger UI at /api/v1/docs
    redoc_url="/api/v1/redoc",    # ReDoc alternative at /api/v1/redoc
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# CORS — allow the frontend (and Swagger UI) to call this API from a browser.
# WHY CORS?
# Browsers block cross-origin requests by default (Same-Origin Policy).
# CORS middleware adds the right headers so browsers permit the requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Request/response logging middleware.

    WHY middleware instead of per-route logging?
    Middleware runs for EVERY request automatically — no need to add
    logging to each route. It also captures errors from routes.

    The `call_next` pattern is the "chain of responsibility":
    middleware passes the request down the chain and gets a response back.
    """
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s → %d  (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all for unhandled exceptions.
    Returns a clean JSON error instead of a 500 HTML page.

    In production, you'd also log to Sentry/Datadog here.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please try again later."},
    )


# ---------------------------------------------------------------------------
# Routers — mount each domain under /api/v1
# ---------------------------------------------------------------------------
# WHY prefix all routes with /api/v1?
# Versioning from day one. When you release breaking changes, you add /api/v2
# alongside /api/v1 without breaking existing clients.
API_PREFIX = settings.api_v1_prefix

app.include_router(auth.router,         prefix=API_PREFIX)
app.include_router(transactions.router, prefix=API_PREFIX)
app.include_router(budgets.router,      prefix=API_PREFIX)
app.include_router(analytics.router,    prefix=API_PREFIX)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    response_model=schemas.HealthResponse,
    tags=["System"],
    summary="Service health check",
)
async def health_check():
    """
    Liveness probe — used by Docker, Railway, and load balancers to verify
    the service is alive. Should always respond quickly (no heavy logic).

    Returns DB connectivity status for a more useful readiness check.
    """
    db_status = "connected"
    try:
        # Use a raw connection to avoid session overhead for this simple check
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("Health check DB error: %s", e)
        db_status = "error"

    return schemas.HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        version="1.0.0",
        database=db_status,
    )


@app.get("/", include_in_schema=False)
async def root():
    """Redirect info for the root path."""
    return {
        "message": "Welcome to Pesa API",
        "docs": "/api/v1/docs",
        "health": "/health",
    }
