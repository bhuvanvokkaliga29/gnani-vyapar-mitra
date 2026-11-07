"""Domain Exceptions for Phase 9.1 Canonical Decision Runtime.

Contract: canonical-decision/v1
"""


class CanonicalRuntimeError(Exception):
    """Base exception for all Canonical Decision Runtime operations."""
    pass


class IncompatibleRuntimeVersionError(CanonicalRuntimeError):
    """Raised when an incoming decision request specifies an unsupported contract version."""
    pass


class DecisionNotFoundError(CanonicalRuntimeError):
    """Raised when a requested decision envelope is not found."""
    pass


class DecisionTenantViolationError(CanonicalRuntimeError):
    """Raised when an operation attempts cross-tenant decision retrieval or mutation."""
    pass


class MissingBuyerIntentInputError(CanonicalRuntimeError):
    """Raised when a decision request provides neither buyer_intent nor raw_prompt."""
    pass


class MerchantInactiveError(CanonicalRuntimeError):
    """Raised when a decision is requested for a merchant that is not active."""
    pass
