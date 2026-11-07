"""Domain exception types for Phase 8.5 Deterministic Learned Candidate Selection."""


class PolicySelectionError(Exception):
    """Base exception for policy selection errors."""
    pass


class EmptyCandidateSetError(PolicySelectionError):
    """Raised when candidate set is empty."""
    pass


class MalformedCandidateError(PolicySelectionError):
    """Raised when a candidate policy fails structural integrity checks."""
    pass


class IncompatibleSelectionVersionError(PolicySelectionError):
    """Raised when request selection_version does not match supported contract."""
    pass


class MerchantSelectionIsolationError(PolicySelectionError):
    """Raised when cross-tenant data access is attempted during candidate selection."""
    pass


class SelectionNotFoundError(PolicySelectionError):
    """Raised when a requested selection record is not found."""
    pass
