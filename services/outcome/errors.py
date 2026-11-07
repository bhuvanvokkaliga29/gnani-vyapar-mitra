"""Domain exceptions for Phase 9.3 Outcome, Feedback & Recovery Loop."""


class OutcomeFeedbackError(Exception):
    """Base exception for all outcome feedback and recovery errors."""
    pass


class IncompatibleFeedbackVersionError(OutcomeFeedbackError):
    """Raised when request specifies an unsupported contract version."""
    pass


class ExecutionRecordNotFoundError(OutcomeFeedbackError):
    """Raised when referenced decision execution ID does not exist."""
    pass


class OutcomeTenantViolationError(OutcomeFeedbackError):
    """Raised when cross-tenant access to execution or outcome is attempted."""
    pass


class UnresolvedTransactionError(OutcomeFeedbackError):
    """Raised when transaction state is uncertain or reconciliation is pending."""
    pass


class LearningEligibilityRejectionError(OutcomeFeedbackError):
    """Raised when an outcome violates the Phase 8.1 learning eligibility firewall."""
    pass


class DuplicateFeedbackError(OutcomeFeedbackError):
    """Raised when concurrent duplicate processing conflicts."""
    pass


class TerminalStateConflictError(OutcomeFeedbackError):
    """Raised when a non-terminal event attempts to overwrite a terminal transaction state."""
    pass


class DownstreamLearningError(OutcomeFeedbackError):
    """Raised when evidence, memory, or model update fails."""
    pass
