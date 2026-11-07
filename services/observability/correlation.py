"""Async-safe correlation and context propagation module for Phase 9.4.

Contract: observability-correlation/v1
Guarantees:
1. Pure contextvars implementation ensuring zero memory or correlation leaks across async tasks or tenants.
2. Structured extraction, validation, and generation of request_id (req_...).
3. Safe propagation across API, service boundaries, audit events, and structured logs.
"""

import uuid
from contextvars import ContextVar, Token
from typing import Optional, Dict, Any

# Async-safe request correlation context variable
_CORRELATION_CTX: ContextVar[Dict[str, Any]] = ContextVar("correlation_ctx", default={})


def generate_request_id() -> str:
    """Generate a canonical, cryptographically unique transport request identifier."""
    return f"req_{uuid.uuid4().hex[:16]}"


def validate_request_id(request_id: Optional[str]) -> str:
    """Validate or sanitize an incoming request identifier.
    
    If invalid or absent, generates a safe canonical request_id.
    Prevents log injection or delimiter forging in request_id.
    """
    if not request_id or not isinstance(request_id, str):
        return generate_request_id()
    
    # Strip whitespace, newlines, control characters
    cleaned = "".join(c for c in request_id.strip() if c.isalnum() or c in ("-", "_"))
    if not cleaned or len(cleaned) > 64:
        return generate_request_id()
    
    return cleaned


def set_correlation_context(
    request_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    opportunity_id: Optional[str] = None,
    decision_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    **kwargs: Any
) -> Token:
    """Bind correlation context for the current async execution scope."""
    curr = dict(_CORRELATION_CTX.get())
    if request_id is not None:
        curr["request_id"] = validate_request_id(request_id)
    if merchant_id is not None:
        curr["merchant_id"] = merchant_id
    if opportunity_id is not None:
        curr["opportunity_id"] = opportunity_id
    if decision_id is not None:
        curr["decision_id"] = decision_id
    if execution_id is not None:
        curr["execution_id"] = execution_id
    for k, v in kwargs.items():
        if v is not None:
            curr[k] = v
    return _CORRELATION_CTX.set(curr)


def reset_correlation_context(token: Token) -> None:
    """Reset correlation context to its previous token state."""
    _CORRELATION_CTX.reset(token)


def get_correlation_context() -> Dict[str, Any]:
    """Retrieve an immutable copy of the current async correlation context."""
    return dict(_CORRELATION_CTX.get())


def get_current_request_id() -> Optional[str]:
    """Get the current request_id if set in the async context."""
    return _CORRELATION_CTX.get().get("request_id")


def get_current_merchant_id() -> Optional[str]:
    """Get the current merchant_id if set in the async context."""
    return _CORRELATION_CTX.get().get("merchant_id")
