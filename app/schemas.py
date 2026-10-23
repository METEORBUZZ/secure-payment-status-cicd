"""Pydantic schemas and request/response models."""

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class PaymentStatus(str, Enum):
    """Supported payment transaction statuses."""

    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentMethod(str, Enum):
    """Supported payment channels."""

    UPI = "UPI"
    CARD = "CARD"
    NETBANKING = "NETBANKING"
    WALLET = "WALLET"


class PaymentCreate(BaseModel):
    """Payload for creating a payment transaction."""

    order_id: str = Field(..., min_length=3, max_length=64, description="Merchant order reference")
    customer_id: str = Field(..., min_length=3, max_length=64, description="Unique customer identifier")
    amount: float = Field(..., gt=0.0, description="Transaction amount in major currency units")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="ISO-4217 3-letter currency code")
    payment_method: PaymentMethod = Field(..., description="Payment instrument")
    status: PaymentStatus = Field(default=PaymentStatus.PENDING, description="Initial status")
    failure_reason: Optional[str] = Field(default=None, max_length=256, description="Reason if marked failed")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        upper = v.upper()
        if not upper.isalpha():
            raise ValueError("Currency code must be 3 alphabetic characters")
        return upper


class PaymentResponse(BaseModel):
    """Response representation of a payment transaction."""

    payment_id: str
    order_id: str
    customer_id: str
    amount: float
    currency: str
    payment_method: str
    status: str
    failure_reason: Optional[str] = None
    created_at: str
    updated_at: str


class PaymentListResponse(BaseModel):
    """Paginated list of payments."""

    total: int
    limit: int
    offset: int
    items: List[PaymentResponse]


class HealthResponse(BaseModel):
    """Service health response for liveness and readiness probes."""

    status: str
    version: str
    environment: str
    database: str
    timestamp: str


class ErrorResponse(BaseModel):
    """Standardized error response payload."""

    error: str
    detail: Any
    timestamp: str
