"""Domain Exceptions for Phase 8.8 Policy Lifecycle Management."""


class PolicyLifecycleError(Exception):
    """Base exception for policy lifecycle and promotion errors."""
    pass


class IncompatibleLifecycleVersionError(PolicyLifecycleError):
    """Raised when an unsupported lifecycle or promotion contract version is supplied."""
    pass


class MerchantLifecycleIsolationError(PolicyLifecycleError):
    """Raised when cross-tenant access to lifecycle states or versions is detected."""
    pass


class PolicyVersionNotFoundError(PolicyLifecycleError):
    """Raised when a specified policy version does not exist in merchant scope."""
    pass


class LifecycleTransitionError(PolicyLifecycleError):
    """Raised when an illegal lifecycle transition is attempted."""
    pass


class ActivePolicyConflictError(PolicyLifecycleError):
    """Raised when optimistic concurrency check fails on expected active predecessor."""
    pass
