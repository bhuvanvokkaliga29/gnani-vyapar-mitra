"""Domain exceptions for Phase 8.2 Learning Objective & Reward Layer."""


class RewardError(Exception):
    """Base domain exception for reward and objective calculations."""
    pass


class IneligibleRewardError(RewardError):
    """Raised when attempting to compute an objective over ineligible or corrupt evidence."""
    pass


class RewardDataUnavailableError(RewardError):
    """Raised when required commercial cost or revenue inputs are missing."""
    pass


class ZeroDenominatorError(RewardError):
    """Raised when the eligible opportunity population is zero (undefined objective)."""
    pass


class RewardAttributionError(RewardError):
    """Raised when reward attribution is ambiguous, mismatched, or cross-tenant."""
    pass


class RewardLeakageError(RewardError):
    """Raised when post-outcome data attempts to contaminate pre-decision state."""
    pass
