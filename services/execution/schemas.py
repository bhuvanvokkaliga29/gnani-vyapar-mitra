"""Pydantic Schemas for Phase 5 Deterministic Commercial Execution Gate."""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from domain.intent_schemas import BuyerIntent
from services.policy.schemas import PolicyProposal, PolicyCandidate, CandidateEconomics


class ExecutionState(str, Enum):
    """Authoritative lifecycle states for policy execution authorization."""
    PROPOSAL_RECEIVED = "PROPOSAL_RECEIVED"
    REVALIDATING = "REVALIDATING"
    EXECUTION_AUTHORIZED = "EXECUTION_AUTHORIZED"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"
    ORDER_CREATE_PENDING = "ORDER_CREATE_PENDING"
    ORDER_CREATED = "ORDER_CREATED"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PAID = "PAID"
    ORDER_CREATE_FAILED = "ORDER_CREATE_FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ExecutionRejectionReason(str, Enum):
    """Machine-readable rejection codes emitted by the execution gate."""
    PROPOSAL_NOT_FOUND = "PROPOSAL_NOT_FOUND"
    MERCHANT_MISMATCH = "MERCHANT_MISMATCH"
    INVALID_PROPOSAL_STATUS = "INVALID_PROPOSAL_STATUS"
    NO_EXECUTABLE_OFFER = "NO_EXECUTABLE_OFFER"
    STALE_CONTEXT = "STALE_CONTEXT"
    PRODUCT_UNAVAILABLE = "PRODUCT_UNAVAILABLE"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    PRICE_CHANGED = "PRICE_CHANGED"
    COST_CHANGED = "COST_CHANGED"
    MARGIN_TOO_LOW = "MARGIN_TOO_LOW"
    DISCOUNT_TOO_HIGH = "DISCOUNT_TOO_HIGH"
    OVER_BUDGET = "OVER_BUDGET"
    BUYER_REQUIREMENT_CHANGED = "BUYER_REQUIREMENT_CHANGED"
    BUYER_EXCLUSION_VIOLATED = "BUYER_EXCLUSION_VIOLATED"
    RELATIONSHIP_INVALID = "RELATIONSHIP_INVALID"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    CONCURRENCY_CONFLICT = "CONCURRENCY_CONFLICT"
    EXECUTION_ALREADY_COMPLETED = "EXECUTION_ALREADY_COMPLETED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    RAZORPAY_ORDER_CREATION_FAILED = "RAZORPAY_ORDER_CREATION_FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class ExecutionAuthorization(BaseModel):
    """Deterministic execution authorization issued by the Execution Gate.

    Contains the authoritative recalculated payable amount. Zero trust is placed
    in client- or LLM-provided monetary figures.
    """
    model_config = ConfigDict(extra="forbid")

    authorization_id: str = Field(description="Unique authorization reference (e.g. auth_...)")
    proposal_id: str = Field(description="Source PolicyProposal ID")
    merchant_id: str = Field(description="Merchant tenant ID")
    candidate_id: str = Field(description="Selected candidate ID")
    authorized_amount_paise: int = Field(ge=0, description="Exact deterministically computed amount in paise")
    currency: str = Field(default="INR", description="3-letter ISO-4217 currency")
    status: str = Field(description="EXECUTION_AUTHORIZED or EXECUTION_REJECTED")
    rejection_reasons: List[str] = Field(default_factory=list, description="Machine-readable rejection codes")
    recalculated_economics: Optional[CandidateEconomics] = Field(default=None, description="Freshly recalculated unit economics")
    receipt: str = Field(description="Deterministic receipt reference for Razorpay (max 40 chars)")
    idempotency_key: str = Field(description="Deterministic idempotency key")
    validation_version: str = Field(default="execution-gate/v1", description="Execution gate validator version")
    source_policy_version: str = Field(default="merchant-policy/v1", description="Policy version of source proposal")
    context_snapshot_timestamp: Optional[datetime] = Field(default=None, description="Timestamp of context snapshot used in proposal")
    authorized_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp authorization was issued")


class PolicyExecuteRequest(BaseModel):
    """Public execution request.

    SECURITY INVARIANT:
    Callers are NOT permitted to submit prices, amounts, margins, or currency.
    All financial values are recomputed server-side from fresh merchant database state.
    """
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(min_length=3, max_length=64, description="Merchant tenant ID")
    proposal_id: str = Field(min_length=5, max_length=64, description="PolicyProposal ID")
    candidate_id: Optional[str] = Field(default=None, description="Specific candidate ID (defaults to proposal.selected_candidate)")
    proposal: Optional[PolicyProposal] = Field(default=None, description="In-memory proposal object for stateless invocation")
    intent: Optional[BuyerIntent] = Field(default=None, description="Associated buyer intent (optional)")
    idempotency_key: Optional[str] = Field(default=None, max_length=128, description="Client idempotency key")


class PolicyExecuteResponse(BaseModel):
    """Authoritative response from the Execution Gate."""
    model_config = ConfigDict(extra="forbid")

    execution_id: str = Field(description="Unique execution record ID")
    status: ExecutionState = Field(description="Current execution lifecycle state")
    authorization: ExecutionAuthorization = Field(description="Deterministic authorization payload")
    order_id: Optional[str] = Field(default=None, description="Internal Order ID (if order created)")
    razorpay_order_id: Optional[str] = Field(default=None, description="Razorpay Test Mode Order ID (if order created)")
    authorized_amount_paise: int = Field(ge=0, description="Authorized payable amount in paise")
    currency: str = Field(default="INR", description="Currency code")
    is_duplicate: bool = Field(default=False, description="True if request replayed existing idempotent execution")
    latency_ms: float = Field(ge=0.0, description="Execution gate processing latency in ms")
