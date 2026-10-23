"""Prometheus custom metrics instrumentation."""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

# Custom or default registry
REGISTRY = CollectorRegistry(auto_describe=True)

# 1. Total HTTP Requests by method, endpoint, and status code
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests handled by the service",
    ["method", "endpoint", "status_code"],
    registry=REGISTRY,
)

# 2. HTTP Request Latency in seconds
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency distribution in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=REGISTRY,
)

# 3. Payment transactions business metrics
PAYMENT_TRANSACTIONS_TOTAL = Counter(
    "payment_transactions_total",
    "Total count of payment transactions processed",
    ["status", "payment_method", "currency"],
    registry=REGISTRY,
)

# 4. Application error events
APP_ERRORS_TOTAL = Counter(
    "app_errors_total",
    "Total count of application error responses",
    ["error_type", "status_code"],
    registry=REGISTRY,
)


def get_latest_metrics() -> bytes:
    """Generate and return current metrics in Prometheus text format."""
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """Return the official Prometheus content type header."""
    return CONTENT_TYPE_LATEST
