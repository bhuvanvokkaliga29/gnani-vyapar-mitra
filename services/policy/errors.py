"""Typed Exceptions for Policy Agent & Commercial Strategy Validation."""


class PolicyError(Exception):
    """Base exception for all Policy Agent errors."""
    pass


class PolicyValidationError(PolicyError):
    """Raised when a candidate or proposal violates deterministic financial or commercial rules."""
    pass


class MerchantContextError(PolicyError):
    """Raised when MerchantCommerceContext is missing, corrupted, or incompatible."""
    pass


class SecurityViolationError(PolicyError):
    """Raised when an attempt to execute financial transactions or bypass security invariants is detected."""
    pass
