"""Audit and immutability error definitions for Phase 9.4."""


class AuditError(Exception):
    """Base exception for all audit domain errors."""
    pass


class AuditImmutabilityViolationError(AuditError):
    """Raised when an attempt is made to update or delete an immutable AuditEvent."""
    pass


class AuditTenantViolationError(AuditError):
    """Raised when an actor attempts cross-tenant access to audit events."""
    pass


class AuditEventNotFoundError(AuditError):
    """Raised when a requested audit event does not exist within the tenant scope."""
    pass
