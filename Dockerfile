# ─────────────────────────────────────────────────────────────
# Dockerfile — Pesa API
# Multi-stage build: keeps the final image lean
# ─────────────────────────────────────────────────────────────

# ── Stage 1: Build the C++ shared library ────────────────────
FROM gcc:13-bookworm AS cpp-builder
# We use a dedicated GCC image rather than installing gcc in the
# final image. The compiled .so is then copied over — no compiler
# bloat in production.

WORKDIR /build
COPY cpp/ .
RUN make

# ── Stage 2: Python runtime ───────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime
# python:3.12-slim: Debian Bookworm with only Python — ~45MB base.
# NOT alpine: asyncpg has a C extension that needs glibc, not musl.

# Install only what's needed at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 \    
    # Required to run the compiled C++ shared library
    curl \
    # Used for health check in docker-compose
    && rm -rf /var/lib/apt/lists/*
    # Always clean apt cache — keeps layer size minimal

WORKDIR /app

# Copy and install Python dependencies first (benefits from Docker layer caching:
# if requirements.txt hasn't changed, this layer is reused on rebuild)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the compiled C++ library from Stage 1
COPY --from=cpp-builder /build/libfinance.so ./cpp/libfinance.so

# Copy application source
COPY api/ ./api/
COPY frontend/ ./frontend/

# Create non-root user (security best practice — never run as root in production)
RUN useradd -m -u 1001 pesa && chown -R pesa:pesa /app
USER pesa

# Expose the application port
EXPOSE 8000

# Health check — Docker / orchestrators use this to determine if the
# container is healthy. If it fails 3 times, the container is restarted.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the app with uvicorn
# --host 0.0.0.0 : listen on all interfaces (required inside Docker)
# --workers 1    : single worker for Railway free tier; increase for production
# --proxy-headers: trust X-Forwarded-Proto from Railway's load balancer
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
