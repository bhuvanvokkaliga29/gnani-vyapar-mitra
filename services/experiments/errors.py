"""Domain exceptions for Phase 7 Controlled Policy Experiments."""


class ExperimentError(Exception):
    """Base exception for all experiment domain errors."""
    pass


class InvalidExperimentStateError(ExperimentError):
    """Raised when an operation is attempted in an incompatible lifecycle state."""
    pass


class CrossTenantViolationError(ExperimentError):
    """Raised when an experiment or observation attempts cross-merchant access."""
    pass


class InvalidPolicyError(ExperimentError):
    """Raised when a control or treatment policy proposal is malformed or rejected."""
    pass


class GuardrailViolationError(ExperimentError):
    """Raised when a proposed policy or experiment violates critical guardrails."""
    pass


class DuplicateObservationError(ExperimentError):
    """Raised when a duplicate observation key is recorded without idempotency."""
    pass


class SecurityBoundaryError(ExperimentError):
    """Raised when client tampering or unauthorized financial override is detected."""
    pass
