"""Pydantic v2 Schemas and Contracts for Phase 9.3 Outcome, Feedback & Recovery Loop.

Contract: outcome-feedback/v1

Defines strongly-typed requests and authoritative outcome feedback processing responses.
Enforces strict invariants:
1. No client authority over financial figures, payment success, reward, or learning eligibility.
2. Information hygiene: Zero leakage of merchant unit costs (COGS), margins, or bandit weights.
3. Explicit separation between transaction outcome states and feedback processing states.

All models enforce ConfigDict(extra="forbid").
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

OUTCOME_FEEDBACK_SCHEMA_VERSION = "outcome-feedback/v1"


class OutcomeStatus(str, Enum):
    """Semantic outcome statuses representing the resolved commercial/transactional outcome."""
    PENDING = "PENDING"
    ORDER_CREATED = "ORDER_CREATED"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_CANCELLED = "PAYMENT_CANCELLED"
    PAYMENT_EXPIRED = "PAYMENT_EXPIRED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    UNRESOLVED = "UNRESOLVED"


class ProcessingState(str, Enum):
    """Internal processing lifecycle states for the feedback-to-learning loop."""
    RECEIVED = "RECEIVED"
    RESOLVING = "RESOLVING"
    RESOLVED = "RESOLVED"
    EVIDENCE_PENDING = "EVIDENCE_PENDING"
    MEMORY_PENDING = "MEMORY_PENDING"
    MODEL_PENDING = "MODEL_PENDING"
    COMPLETED = "COMPLETED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"


class OutcomeProcessRequest(BaseModel):
    """Request payload to process or reconcile an execution outcome.

    SECURITY INVARIANT:
    Clients CANNOT specify payment success, transaction amount, contribution,
    reward, learning eligibility, or model update parameters.
    All transaction facts are derived server-side from authoritative Phase 5 data.
    """
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(..., min_length=1, max_length=64, description="Tenant merchant identifier")
    execution_id: str = Field(..., min_length=1, max_length=64, description="Phase 9.2 boundary execution ID (dexec_...)")
    idempotency_key: Optional[str] = Field(default=None, max_length=128, description="Optional client idempotency key")


class OutcomeProcessResponse(BaseModel):
    """Authoritative response returned by the Phase 9.3 Feedback Loop.

    Contract: outcome-feedback/v1

    INFORMATION HYGIENE INVARIANT:
    Contains customer- and merchant-safe outcome references.
    MUST NEVER leak merchant unit costs (COGS), margins, or internal model weights.
    """
    model_config = ConfigDict(extra="forbid")

    outcome_id: str = Field(..., description="Unique outcome record ID (out_...)")
    merchant_id: str = Field(..., description="Tenant merchant ID")
    opportunity_id: str = Field(..., description="Commercial opportunity identifier")
    decision_id: str = Field(..., description="Referenced Phase 9.1 decision ID (dec_...)")
    execution_id: str = Field(..., description="Referenced Phase 9.2 boundary execution ID (dexec_...)")
    order_id: Optional[str] = Field(default=None, description="Internal order ID if created")
    razorpay_order_id: Optional[str] = Field(default=None, description="Razorpay order ID if created")
    razorpay_payment_id: Optional[str] = Field(default=None, description="Authoritative Razorpay payment ID (pay_...)")
    transaction_state: str = Field(..., description="Authoritative Phase 5 TransactionState string")
    outcome_status: OutcomeStatus = Field(..., description="Semantic outcome status")
    processing_state: ProcessingState = Field(..., description="Internal processing state")
    is_terminal: bool = Field(..., description="True if transaction outcome is final and non-mutable")
    learning_eligible: bool = Field(..., description="True if outcome is eligible for Phase 8.1 evidence & learning")
    evidence_id: Optional[str] = Field(default=None, description="Phase 8.1 evidence ID (evi_...) if ingested")
    memory_id: Optional[str] = Field(default=None, description="Phase 8.3 memory record ID (mem_...) if recorded")
    realized_revenue_paise: Optional[int] = Field(default=None, ge=0, description="Verified transaction revenue in integer paise")
    reward_contribution_paise: Optional[int] = Field(default=None, description="Authoritative gross contribution reward in integer paise")
    rejection_reasons: List[str] = Field(default_factory=list, description="Machine-readable rejection reasons if not eligible")
    is_duplicate: bool = Field(default=False, description="True if replayed idempotently from ledger")
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of processing")
    feedback_version: str = Field(default=OUTCOME_FEEDBACK_SCHEMA_VERSION, description="Contract version")
