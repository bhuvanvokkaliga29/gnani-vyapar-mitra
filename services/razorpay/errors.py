"""Structured Exceptions for Razorpay Adapter."""

from typing import Optional, Dict, Any


class RazorpayError(Exception):
    """Base exception for all Razorpay adapter errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class RazorpayTimeoutError(RazorpayError):
    """Raised when an HTTP request to Razorpay times out (indicates uncertain transaction state)."""
    pass


class RazorpayNetworkError(RazorpayError):
    """Raised on socket or connection errors reaching Razorpay."""
    pass


class RazorpayAuthenticationError(RazorpayError):
    """Raised when Razorpay rejects credentials (HTTP 401)."""
    pass


class RazorpayBadRequestError(RazorpayError):
    """Raised when request parameters are invalid (HTTP 400)."""
    pass


class RazorpayNotFoundError(RazorpayError):
    """Raised when the requested resource does not exist (HTTP 404)."""
    pass


class RazorpaySignatureVerificationError(RazorpayError):
    """Raised when inbound webhook HMAC signature is missing or does not match."""
    pass
