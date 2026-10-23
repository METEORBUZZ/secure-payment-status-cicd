# ==============================================================================
# STAGE 1: Builder
# - Uses pinned Python Alpine base image
# - Installs pinned wheel dependencies and strips build packages
# ==============================================================================
FROM python:3.11.9-alpine3.20 AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build dependencies
RUN apk add --no-cache gcc musl-dev libffi-dev

# Create isolated virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy pinned requirements and install wheels
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    # Strip unnecessary pip, setuptools, and compiled cache files from final runtime
    find /opt/venv -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true && \
    rm -rf /opt/venv/lib/python*/site-packages/pip* /opt/venv/lib/python*/site-packages/setuptools*


# ==============================================================================
# STAGE 2: Production Runner
# - Minimal runtime image (<150 MB requirement)
# - Runs as an unprivileged, non-root user (UID 10001)
# ==============================================================================
FROM python:3.11.9-alpine3.20 AS runner

LABEL maintainer="DevOps Team <devops@punefintech.internal>" \
      service="payment-status-service" \
      version="1.0.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV="production" \
    PORT=8000 \
    DB_PATH="/data/payments.db"

# Upgrade security packages and create non-root user
RUN apk update && apk upgrade --no-cache && \
    addgroup -g 10001 appgroup && \
    adduser -u 10001 -G appgroup -s /sbin/nologin -D -h /app appuser && \
    mkdir -p /app /data && \
    chown -R appuser:appgroup /app /data && \
    rm -rf /var/cache/apk/* /tmp/*

# Copy pre-built virtual environment from builder stage
COPY --from=builder --chown=appuser:appgroup /opt/venv /opt/venv

WORKDIR /app

# Copy application source code with non-root ownership
COPY --chown=appuser:appgroup app/ ./app

# Drop all privileges and switch to unprivileged user
USER 10001:10001

# Document container port
EXPOSE 8000

# Container healthcheck using standard library urllib
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).getcode() == 200 else 1)"

# Production ASGI server launch (single worker per container, horizontally scaled via Kubernetes replicas)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--access-log"]
