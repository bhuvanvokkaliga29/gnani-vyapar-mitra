"""Domain exceptions for Constrained Exploration / Exploitation Engine.

Contract: policy-exploration/v1
"""


class ExplorationError(Exception):
    """Base exception for all exploration engine errors."""
    pass


class IncompatibleExplorationVersionError(ExplorationError):
    """Raised when request specifies an unsupported exploration contract version."""
    pass


class MerchantExplorationIsolationError(ExplorationError):
    """Raised when tenant boundary is violated or cross-merchant access is attempted."""
    pass


class ExplorationDecisionNotFoundError(ExplorationError):
    """Raised when a requested exploration decision ID cannot be found."""
    pass


class ExplorationConcurrencyError(ExplorationError):
    """Raised when optimistic locking detects concurrent modification of exploration state."""
    pass
