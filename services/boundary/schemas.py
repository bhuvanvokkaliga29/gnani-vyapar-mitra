"""Pydantic schemas for Phase 9.2 Active Policy + Safety + Execution Boundary.

Contract: execution-boundary/v1

Defines strongly-typed requests and authoritative boundary execution responses.
Enforces strict invariants:
1. No client authority over prices, margins, safety checks, or authorizations.
2. Information hygiene: Zero leakage of merchant unit costs (COGS), margins, or internal scores.
3. Server-derived, single-use execution authorization binding.

All models enforce ConfigDict(extra="forbid").
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

EXECUTION_BOUNDARY_SCHEMA_VERSION = "execution-boundary/v1"


class ExecutionBoundaryStatus(str, Enum):
    """Authoritative lifecycle and outcome statuses for execution boundary traversal."""
    PENDING_EXECUTION_GATE = "PENDING_EXECUTION_GATE"
    ACTIVE_POLICY_VERIFIED = "ACTIVE_POLICY_VERIFIED"
    SAFETY_VERIFIED = "SAFETY_VERIFIED"
    EXECUTION_AUTHORIZED = "EXECUTION_AUTHORIZED"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    DECISION_STALE = "DECISION_STALE"
    POLICY_NOT_ACTIVE = "POLICY_NOT_ACTIVE"
    POLICY_RETIRED = "POLICY_RETIRED"
    POLICY_ROLLED_BACK = "POLICY_ROLLED_BACK"
    SAFETY_REJECTED = "SAFETY_REJECTED"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"
    EXECUTION_CONFLICT = "EXECUTION_CONFLICT"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    INVALID_DECISION = "INVALID_DECISION"


class DecisionExecuteRequest(BaseModel):
    """Request payload to execute a canonical decision envelope.

    SECURITY INVARIANT:
    Clients CANNOT specify prices, discounts, margins, execution authorization tokens,
    or safety approval flags. All financial figures and safety authorizations
    are derived server-side from authoritative database state.
    """
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(..., min_length=1, max_length=64, description="Tenant merchant identifier")
    idempotency_key: Optional[str] = Field(default=None, max_length=128, description="Optional client idempotency key")


class DecisionExecuteResponse(BaseModel):
    """Authoritative response returned by the Phase 9.2 Execution Boundary.

    Contract: execution-boundary/v1

    INFORMATION HYGIENE INVARIANT:
    Contains strictly customer- and merchant-safe execution references.
    MUST NEVER leak COGS, gross margins, unit costs, or internal bandit weights.
    """
    model_config = ConfigDict(extra="forbid")

    execution_id: str = Field(..., description="Unique boundary execution ID (dexec_...)")
    decision_id: str = Field(..., description="Referenced Phase 9.1 decision ID (dec_...)")
    merchant_id: str = Field(..., description="Tenant merchant ID")
    opportunity_id: str = Field(..., description="Commercial opportunity identifier")
    boundary_status: ExecutionBoundaryStatus = Field(..., description="Final outcome status of boundary evaluation")
    execution_authorized: bool = Field(..., description="True if decision passed all gates and was authorized for execution")
    authorization_id: Optional[str] = Field(default=None, description="Server-issued single-use authorization token (eauth_...)")
    safety_check_id: Optional[str] = Field(default=None, description="Authoritative Phase 8.6 safety check ID")
    phase5_execution_id: Optional[str] = Field(default=None, description="Authoritative Phase 5 ExecutionRecord ID (exec_...)")
    order_id: Optional[str] = Field(default=None, description="Internal order ID if created by Phase 5")
    razorpay_order_id: Optional[str] = Field(default=None, description="Razorpay Test Mode order ID if created by Phase 5")
    authorized_amount_paise: Optional[int] = Field(default=None, ge=0, description="Exact server-derived payable amount in integer paise")
    currency: str = Field(default="INR", description="3-letter currency code")
    rejection_reasons: List[str] = Field(default_factory=list, description="Machine-readable rejection codes if boundary failed")
    is_duplicate: bool = Field(default=False, description="True if replayed from boundary idempotency ledger")
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of execution attempt")
    boundary_version: str = Field(default=EXECUTION_BOUNDARY_SCHEMA_VERSION, description="Contract version")
