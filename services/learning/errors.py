"""Domain exceptions for Phase 8.1 Merchant Policy Learning Evidence."""


class LearningError(Exception):
    """Base exception for learning and evidence domain errors."""
    pass


class InvalidEvidenceError(LearningError):
    """Raised when an evidence record fails schema, provenance, or invariant checks."""
    pass


class CrossTenantLearningError(LearningError):
    """Raised when an operation attempts to access or attach evidence across merchant boundaries."""
    pass


class EvidenceImmutabilityError(LearningError):
    """Raised when an attempt is made to mutate or overwrite finalized learning evidence."""
    pass


class DuplicateEvidenceError(LearningError):
    """Raised when an observation has already been ingested into the learning store."""
    pass


class SecurityBoundaryError(LearningError):
    """Raised when client supplies fake metrics, fake rewards, or unauthorized learning actions."""
    pass
