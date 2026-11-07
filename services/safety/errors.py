"""Domain Exceptions for Deterministic Policy Safety & Admissibility Gate.

Contract Version: policy-safety/v1
"""


class PolicySafetyError(Exception):
    """Base exception for Phase 8.6 policy safety errors."""
    pass


class IncompatibleSafetyVersionError(PolicySafetyError):
    """Raised when request provides an incompatible safety contract version."""
    pass


class MerchantSafetyIsolationError(PolicySafetyError):
    """Raised when cross-tenant safety record access or evaluation is attempted."""
    pass


class SafetyCheckNotFoundError(PolicySafetyError):
    """Raised when requested safety check ID does not exist."""
    pass
