"""Domain Exception Hierarchy for Phase 8.9 Closed-Loop Learning Evaluation."""


class ClosedLoopEvaluationError(Exception):
    """Base exception for all closed-loop evaluation errors."""
    pass


class IncompatibleEvaluationVersionError(ClosedLoopEvaluationError):
    """Raised when request specifies an unsupported closed-loop evaluation contract version."""
    pass


class EvaluationNotFoundError(ClosedLoopEvaluationError):
    """Raised when an evaluation run cannot be located."""
    pass


class EvaluationTenantViolationError(ClosedLoopEvaluationError):
    """Raised when cross-tenant data access or isolation violation is detected."""
    pass


class EvaluationStateConflictError(ClosedLoopEvaluationError):
    """Raised when an evaluation run is in an incompatible state for the requested action."""
    pass


class DatasetNotFoundError(ClosedLoopEvaluationError):
    """Raised when the specified scenario dataset is missing or unresolvable."""
    pass


class EvaluationExecutionError(ClosedLoopEvaluationError):
    """Raised when unrecoverable failure occurs during closed-loop execution."""
    pass
