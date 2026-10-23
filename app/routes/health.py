"""Health and readiness probe endpoint."""

from datetime import datetime, timezone
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import check_db_health
from app.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check for liveness and readiness probes",
    responses={
        200: {"description": "Service is healthy and ready to accept traffic"},
        503: {"description": "Service is degraded or database is unreachable"},
    },
)
def get_health():
    """Verify application health and database connectivity."""
    db_ok = check_db_health()
    now_utc = datetime.now(timezone.utc).isoformat()

    if db_ok:
        payload = HealthResponse(
            status="UP",
            version=settings.APP_VERSION,
            environment=settings.APP_ENV,
            database="CONNECTED",
            timestamp=now_utc,
        )
        return payload

    payload = HealthResponse(
        status="DEGRADED",
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        database="UNAVAILABLE",
        timestamp=now_utc,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )
