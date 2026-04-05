# ─────────────────────────────────────────────────────────────
# Dockerfile — Pesa API
# Multi-stage build: Stage 1 compiles C++, Stage 2 is Python runtime
# ─────────────────────────────────────────────────────────────

# ── Stage 1: Build the C++ shared library ────────────────────
FROM gcc:13-bookworm AS cpp-builder

WORKDIR /build
COPY cpp/ .
RUN make

# ── Stage 2: Python runtime ───────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# Install runtime dependencies — NO inline comments after backslashes,
# that breaks the shell continuation and causes build failures on Railway
RUN apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (Docker layer cache: only re-runs if
# requirements.txt changes, saving ~60s on every code-only redeploy)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy compiled C++ library from Stage 1
COPY --from=cpp-builder /build/libfinance.so ./cpp/libfinance.so

# Copy application source
COPY api/ ./api/
COPY frontend/ ./frontend/

# Non-root user — never run as root in production
RUN useradd -m -u 1001 pesa && chown -R pesa:pesa /app
USER pesa

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
