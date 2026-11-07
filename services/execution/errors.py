"""Exception hierarchy for Phase 5 Execution Gate."""

class ExecutionGateError(Exception):
    """Base exception for execution gate errors."""
    def __init__(self, message: str, code: str = "EXECUTION_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class ExecutionValidationError(ExecutionGateError):
    """Raised when deterministic execution validation fails."""
    def __init__(self, message: str, code: str = "VALIDATION_FAILED", reasons: list = None):
        super().__init__(message, code)
        self.reasons = reasons or []


class StaleContextError(ExecutionValidationError):
    """Raised when proposal references state that has since drifted."""
    def __init__(self, message: str, reasons: list = None):
        super().__init__(message, code="STALE_CONTEXT", reasons=reasons)


class ConcurrencyConflictError(ExecutionGateError):
    """Raised when an inventory race or concurrent modification is detected."""
    def __init__(self, message: str):
        super().__init__(message, code="CONCURRENCY_CONFLICT")


class IdempotencyError(ExecutionGateError):
    """Raised when an idempotency conflict or duplicate submission issue occurs."""
    def __init__(self, message: str):
        super().__init__(message, code="IDEMPOTENCY_CONFLICT")
