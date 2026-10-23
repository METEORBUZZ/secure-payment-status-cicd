"""Payment status and lifecycle endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.database import (
    count_payments,
    get_payment_by_id,
    insert_payment,
    list_payments,
)
from app.metrics import APP_ERRORS_TOTAL, PAYMENT_TRANSACTIONS_TOTAL
from app.schemas import (
    ErrorResponse,
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    PaymentStatus,
)

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


def _generate_payment_id() -> str:
    """Generate realistic fintech payment reference ID."""
    return f"pay_{uuid.uuid4().hex[:16]}"


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new payment transaction",
    responses={
        201: {"description": "Payment successfully initiated and recorded"},
        422: {"description": "Request payload validation failed", "model": ErrorResponse},
    },
)
def create_payment(payload: PaymentCreate):
    """Initiate a payment transaction and store its initial status."""
    now = datetime.now(timezone.utc).isoformat()
    payment_id = _generate_payment_id()

    payment_data = {
        "payment_id": payment_id,
        "order_id": payload.order_id,
        "customer_id": payload.customer_id,
        "amount": round(float(payload.amount), 2),
        "currency": payload.currency,
        "payment_method": payload.payment_method.value,
        "status": payload.status.value,
        "failure_reason": payload.failure_reason,
        "created_at": now,
        "updated_at": now,
    }

    insert_payment(payment_data)

    # Record Prometheus business metric
    PAYMENT_TRANSACTIONS_TOTAL.labels(
        status=payload.status.value,
        payment_method=payload.payment_method.value,
        currency=payload.currency,
    ).inc()

    return payment_data


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment details by payment_id",
    responses={
        200: {"description": "Payment found and returned"},
        404: {"description": "Payment ID not found", "model": ErrorResponse},
    },
)
def get_payment(payment_id: str):
    """Fetch status and details of an existing payment."""
    # Basic validation for payment_id format
    if not payment_id or len(payment_id.strip()) == 0:
        APP_ERRORS_TOTAL.labels(error_type="validation_error", status_code="400").inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment ID cannot be empty",
        )

    payment = get_payment_by_id(payment_id.strip())
    if not payment:
        APP_ERRORS_TOTAL.labels(error_type="not_found", status_code="404").inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID '{payment_id}' was not found",
        )

    return payment


@router.get(
    "",
    response_model=PaymentListResponse,
    summary="List payments with filtering and pagination",
)
def get_all_payments(
    status_filter: Optional[PaymentStatus] = Query(None, alias="status"),
    customer_id: Optional[str] = Query(None, min_length=1, max_length=64),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Retrieve payments with optional status/customer filtering and pagination."""
    status_val = status_filter.value if status_filter else None
    items = list_payments(status=status_val, customer_id=customer_id, limit=limit, offset=offset)
    total = count_payments(status=status_val, customer_id=customer_id)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }
