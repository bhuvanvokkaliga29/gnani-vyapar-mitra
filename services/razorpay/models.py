"""Pydantic Models for Razorpay API Requests, Responses, and Webhooks."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class RazorpayOrderCreateRequest(BaseModel):
    """Payload sent to POST /v1/orders."""
    amount: int = Field(gt=0, description="Amount in integer minor units (paise)")
    currency: str = Field(default="INR", max_length=3, description="ISO 4217 3-letter currency code")
    receipt: str = Field(max_length=40, description="Internal decision or transaction reference ID")
    notes: Optional[Dict[str, Any]] = Field(default=None, description="Metadata dictionary (max 15 pairs)")
    payment_capture: int = Field(default=1, description="1 for auto-capture, 0 for manual capture")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        code = v.upper()
        if code != "INR":
            raise ValueError(f"Currency '{v}' is not supported for Phase 1. Only 'INR' is allowed.")
        return code


class RazorpayOrderResponse(BaseModel):
    """Response returned by POST or GET /v1/orders."""
    id: str = Field(description="Razorpay order ID (order_...)")
    entity: str = Field(default="order")
    amount: int = Field(description="Total order amount in paise")
    amount_paid: int = Field(default=0, description="Amount paid so far in paise")
    amount_due: Optional[int] = Field(default=None, description="Remaining balance in paise")
    currency: str = Field(default="INR")
    receipt: Optional[str] = Field(default=None)
    status: str = Field(description="Status string e.g. created, attempted, paid")
    created_at: Optional[int] = Field(default=None, description="Unix timestamp in seconds")
    notes: Optional[Dict[str, Any]] = Field(default=None)


class RazorpayPaymentItem(BaseModel):
    """Individual payment record from Razorpay."""
    id: str = Field(description="Razorpay payment ID (pay_...)")
    entity: str = Field(default="payment")
    amount: int = Field(description="Payment amount in paise")
    currency: str = Field(default="INR")
    status: str = Field(description="Payment status: authorized, captured, failed")
    order_id: Optional[str] = Field(default=None)
    method: Optional[str] = Field(default=None)
    captured: bool = Field(default=False)
    error_code: Optional[str] = Field(default=None)
    error_description: Optional[str] = Field(default=None)
    created_at: Optional[int] = Field(default=None, description="Unix timestamp in seconds")


class RazorpayPaymentCollection(BaseModel):
    """Collection response from GET /v1/orders/{order_id}/payments."""
    entity: str = Field(default="collection")
    count: int = Field(description="Count of payments returned")
    items: List[RazorpayPaymentItem] = Field(default_factory=list)


class RazorpayWebhookPayload(BaseModel):
    """Typed representation of an inbound Razorpay webhook."""
    entity: str = Field(default="event")
    account_id: Optional[str] = Field(default=None)
    event: str = Field(description="Event name e.g. order.paid, payment.captured")
    contains: Optional[List[str]] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(description="Entity container dictionary")
    created_at: Optional[int] = Field(default=None, description="Unix timestamp")
