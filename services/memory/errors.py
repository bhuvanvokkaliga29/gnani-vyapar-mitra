"""Domain exceptions for Phase 8.3 Merchant Policy Memory layer."""


class MemoryError(Exception):
    """Base domain exception for policy memory operations."""
    pass


class DuplicateMemoryRecordError(MemoryError):
    """Raised when an attempt is made to insert conflicting data for an existing memory record."""
    pass


class MemoryTenantViolationError(MemoryError):
    """Raised when an operation attempts cross-tenant access to policy history."""
    pass


class MemoryProvenanceError(MemoryError):
    """Raised when required upstream evidence or reward provenance is missing or invalid."""
    pass


class MemoryImmutableError(MemoryError):
    """Raised when an illegal attempt is made to modify or delete immutable historical memory."""
    pass
