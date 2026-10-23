"""FastAPI Application Entrypoint for PuneFinTech Payment Status Service."""

import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import close_db_connection, init_db
from app.metrics import (
    APP_ERRORS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    get_latest_metrics,
    get_metrics_content_type,
)
from app.routes import health, payments

# Configure structured logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("payment-status-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for database initialization and cleanup."""
    logger.info("Initializing database schema at: %s", settings.DB_PATH)
    init_db()
    logger.info("Service initialized successfully (Env: %s)", settings.APP_ENV)
    yield
    logger.info("Shutting down service and cleaning up resources...")
    close_db_connection()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Fictional Pune FinTech REST API for tracking payment status "
        "with CI/CD, security scanning, and Prometheus monitoring."
    ),
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
)


@app.middleware("http")
async def prometheus_metrics_middleware(request: Request, call_next):
    """Middleware for tracking request latency, status codes, and Prometheus metrics."""
    start_time = time.perf_counter()
    endpoint = request.url.path

    # Avoid high cardinality for payment IDs in Prometheus endpoint label
    normalized_endpoint = endpoint
    if endpoint.startswith("/api/v1/payments/") and endpoint != "/api/v1/payments":
        normalized_endpoint = "/api/v1/payments/{payment_id}"

    try:
        response = await call_next(request)
        status_code = str(response.status_code)
    except Exception as exc:
        status_code = "500"
        APP_ERRORS_TOTAL.labels(error_type=type(exc).__name__, status_code="500").inc()
        logger.exception("Unhandled server exception during request processing: %s", exc)
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "detail": "An internal unexpected server error occurred",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    finally:
        duration = time.perf_counter() - start_time
        # Record HTTP latency and request count
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            endpoint=normalized_endpoint,
        ).observe(duration)

        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            endpoint=normalized_endpoint,
            status_code=status_code,
        ).inc()

    return response


# Exception Handlers
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Handle explicit HTTPExceptions with consistent JSON schema."""
    APP_ERRORS_TOTAL.labels(error_type="HTTPException", status_code=str(exc.status_code)).inc()
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "detail": exc.detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic schema validation failures with 422."""
    APP_ERRORS_TOTAL.labels(error_type="ValidationError", status_code="422").inc()
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "detail": jsonable_encoder(exc.errors()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch unhandled runtime errors with 500."""
    logger.exception("Unhandled server exception: %s", exc)
    APP_ERRORS_TOTAL.labels(error_type="InternalServerError", status_code="500").inc()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "detail": "An internal unexpected server error occurred",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# Prometheus metrics endpoint
@app.get("/metrics", include_in_schema=False)
def metrics():
    """Prometheus metrics scrape target."""
    return Response(
        content=get_latest_metrics(),
        media_type=get_metrics_content_type(),
    )


# Include Sub-Routers
app.include_router(health.router)
app.include_router(payments.router)
