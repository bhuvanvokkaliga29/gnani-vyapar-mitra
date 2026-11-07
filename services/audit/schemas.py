"""Audit schemas and contract definitions for Phase 9.4.

Contract: audit-event/v1
Enforces strict schema validation, immutability contracts, and information hygiene.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

AUDIT_SCHEMA_VERSION = "audit-event/v1"


class AuditEventRecordSchema(BaseModel):
    """Schema representing an immutable, durable audit event."""
    model_config = ConfigDict(extra="forbid")

    audit_event_id: str = Field(description="Unique audit identifier (aud_...)")
    merchant_id: Optional[str] = Field(default=None, description="Tenant merchant identifier if tenant-scoped")
    entity_type: str = Field(description="Domain entity type (DECISION, EXECUTION, ORDER, OUTCOME, etc.)")
    entity_id: str = Field(description="Domain entity identifier")
    actor: str = Field(description="Actor/component initiating the action")
    action: str = Field(description="Domain action name")
    request_id: Optional[str] = Field(default=None, description="Transport request correlation identifier")
    opportunity_id: Optional[str] = Field(default=None, description="Commercial opportunity identifier")
    decision_id: Optional[str] = Field(default=None, description="Canonical decision identifier")
    execution_id: Optional[str] = Field(default=None, description="Decision execution identifier")
    outcome_id: Optional[str] = Field(default=None, description="Outcome feedback identifier")
    evidence_id: Optional[str] = Field(default=None, description="Learning evidence identifier")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Sanitized event metadata snapshot")
    created_at: datetime = Field(description="Server UTC timestamp of event recording")
    audit_version: str = Field(default=AUDIT_SCHEMA_VERSION, description="Audit schema version")


class AuditQueryResponse(BaseModel):
    """Schema representing tenant-scoped audit query results."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(description="Query tenant scope")
    total_count: int = Field(description="Number of matching audit events")
    events: List[AuditEventRecordSchema] = Field(description="List of matching immutable audit events")
    audit_version: str = Field(default=AUDIT_SCHEMA_VERSION, description="Audit contract version")
