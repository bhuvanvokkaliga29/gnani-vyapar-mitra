"""Unit tests for strict integer minor units (paise) money representation."""

import pytest
from pydantic import ValidationError
from services.razorpay.models import RazorpayOrderCreateRequest


def test_positive_integer_paise_accepted():
    """Valid positive integer amount in paise must succeed."""
    req = RazorpayOrderCreateRequest(
        amount=150000,  # ₹1,500.00
        currency="INR",
        receipt="rec_test_123"
    )
    assert req.amount == 150000
    assert isinstance(req.amount, int)


def test_negative_or_zero_amount_rejected():
    """Negative and zero amounts must be rejected by validation."""
    with pytest.raises(ValidationError):
        RazorpayOrderCreateRequest(amount=0, currency="INR", receipt="rec_0")

    with pytest.raises(ValidationError):
        RazorpayOrderCreateRequest(amount=-500, currency="INR", receipt="rec_neg")


def test_unsupported_currency_rejected():
    """Non-INR currency codes must be rejected in Phase 1."""
    with pytest.raises(ValidationError, match="Only 'INR' is allowed"):
        RazorpayOrderCreateRequest(amount=1000, currency="USD", receipt="rec_usd")


def test_receipt_length_limit():
    """Receipt strings exceeding 40 characters must be rejected."""
    long_receipt = "a" * 41
    with pytest.raises(ValidationError):
        RazorpayOrderCreateRequest(amount=1000, currency="INR", receipt=long_receipt)
