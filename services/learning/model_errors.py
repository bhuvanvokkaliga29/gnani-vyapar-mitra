"""Domain exceptions for Phase 8.4 Merchant Policy Learning Model."""


class LearningModelError(Exception):
    """Base domain exception for statistical policy learning model errors."""
    pass


class IncompatibleFeatureSchemaError(LearningModelError):
    """Raised when an extracted feature vector or schema version is incompatible with the model."""
    pass


class CorruptedModelStateError(LearningModelError):
    """Raised when model matrices or parameters contain invalid dimensions, NaN, or infinite values."""
    pass


class ConcurrentModelUpdateError(LearningModelError):
    """Raised when optimistic concurrency detects a lost update race condition."""
    pass


class MerchantModelIsolationError(LearningModelError):
    """Raised when an unauthorized cross-tenant model operation is attempted."""
    pass
