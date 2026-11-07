"""Domain exceptions for Phase 9.2 Execution Boundary."""


class ExecutionBoundaryError(Exception):
    """Base exception for all execution boundary errors."""
    pass


class IncompatibleBoundaryVersionError(ExecutionBoundaryError):
    """Raised when client supplies unsupported boundary schema version."""
    pass


class DecisionNotFoundError(ExecutionBoundaryError):
    """Raised when referenced decision_id does not exist."""
    pass


class DecisionTenantViolationError(ExecutionBoundaryError):
    """Raised when cross-tenant decision execution attempt is detected."""
    pass


class DecisionStaleError(ExecutionBoundaryError):
    """Raised when decision creation timestamp exceeds the validity TTL."""
    pass


class PolicyLifecycleStateError(ExecutionBoundaryError):
    """Raised when policy is not active, retired, or rolled back."""
    pass


class SafetyRejectionError(ExecutionBoundaryError):
    """Raised when Phase 8.6 commercial safety re-evaluation rejects the proposal."""
    pass


class ExecutionAuthorizationError(ExecutionBoundaryError):
    """Raised when authorization token is missing, forged, already consumed, or mismatched."""
    pass


class ExecutionConflictError(ExecutionBoundaryError):
    """Raised when concurrent execution race causes a state conflict."""
    pass
