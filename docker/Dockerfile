# syntax=docker/dockerfile:1

# =============================================================================
# Base Stage - Common setup for all environments
# =============================================================================
FROM ghcr.io/astral-sh/uv:0.9.21-python3.14-trixie AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    make \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (same UID as host for file permissions)
RUN groupadd -r appuser -g 1000 && \
    useradd -r -u 1000 -g appuser -m -s /bin/bash appuser

# Set working directory and ownership
WORKDIR /app
RUN chown appuser:appuser /app

# Switch to non-root user for all subsequent operations
USER appuser

# Set environment variables for UV and Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# =============================================================================
# Development Stage - Hot reload, full tooling
# =============================================================================
FROM base AS development

# Copy dependency files and source (as appuser)
# Note: Source and README needed before uv sync because uv_build builds the local package
COPY --chown=appuser:appuser pyproject.toml README.md ./
COPY --chown=appuser:appuser uv.loc[k] ./
COPY --chown=appuser:appuser src/ ./src/

# Install dependencies (creates uv.lock if it doesn't exist)
RUN uv sync --all-groups

# Copy tests explicitly (excluded by .dockerignore for prod, but needed for dev/CI)
COPY --chown=appuser:appuser tests/ ./tests/

# Copy remaining application code (as appuser)
COPY --chown=appuser:appuser . .

# Development command - Start worker with reload
CMD ["sh", "-c", "echo 'Starting TaskIQ worker...' && uv run taskiq worker dashtam_jobs.broker:broker --ack-type when_executed"]

# =============================================================================
# Builder Stage - Production dependency installation
# =============================================================================
FROM base AS builder

# Copy dependency files
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Install production dependencies only (no dev dependencies)
RUN uv sync --frozen --no-dev

# =============================================================================
# Production Stage - Minimal runtime
# =============================================================================
FROM python:3.14-slim AS production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser -g 1000 && \
    useradd -r -u 1000 -g appuser -m -s /bin/bash appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy virtual environment from builder (as appuser)
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code (as appuser)
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Health check - verify worker process is running
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD pgrep -f "taskiq worker" || exit 1

# Production command - worker with acknowledgement safety
CMD ["uv", "run", "taskiq", "worker", "dashtam_jobs.broker:broker", "--ack-type", "when_executed"]
