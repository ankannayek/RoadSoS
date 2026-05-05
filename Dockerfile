# ── Stage 1: Build dependencies ────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies required for asyncpg, geoalchemy2, and cryptography.
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Production image ─────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Runtime dependencies only (no gcc/build tools).
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r roadsos && useradd -r -g roadsos -s /bin/false roadsos

COPY --from=builder /install /usr/local

COPY . .

# Health check — hits the lightweight /health/live endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health/live || exit 1

# Run as non-root for security.
USER roadsos

EXPOSE 8000

# Uvicorn with 4 workers for production. Adjust via UVICORN_WORKERS env var.
# The --proxy-headers flag enables trust of X-Forwarded-For from a reverse proxy.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-4} --proxy-headers --forwarded-allow-ips='*' --access-log"]
