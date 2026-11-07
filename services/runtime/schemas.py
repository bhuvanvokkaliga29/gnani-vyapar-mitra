"""Pydantic schemas for Phase 9.1 Canonical Decision Runtime.

Contract: canonical-decision/v1

Defines strongly-typed input requests and the authoritative DecisionEnvelope.
Enforces strict separation between:
1. Public Buyer-facing Commerce Offer (Zero internal margin/COGS leakage).
2. Merchant Internal Decision & Economics View (COGS, margins, model telemetry).
3. Non-Authorization Invariant (Phase 9.1 produces canonical decisions; execution
   authorization is strictly deferred to Phase 9.2).

All models enforce ConfigDict(extra="forbid").
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator

from domain.intent_schemas import BuyerIntent
from services.exploration.schemas import MerchantExplorationConfig

CANONICAL_DECISION_SCHEMA_VERSION = "canonical-decision/v1"


class DecisionMode(str, Enum):
    """Execution mode of the decision."""
    EXPLOIT = "EXPLOIT"
    EXPLORE = "EXPLORE"


class IntentSummary(BaseModel):
    """Structured summary of the buyer intent driving the decision."""
    model_config = ConfigDict(extra="forbid")

    category: Optional[str] = "General"
    use_case: Optional[str] = None
    quantity: Optional[int] = 1
    budget_paise: Optional[int] = None
    hard_requirements: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)
    raw_prompt: Optional[str] = None


class BuyerOfferView(BaseModel):
    """Clean, public buyer-facing offer view.

    STRICT INFORMATION HYGIENE INVARIANT:
    This view contains ONLY customer-facing offer terms.
    It MUST NEVER expose COGS, gross margins, unit costs, or merchant profit thresholds.
    """
    model_config = ConfigDict(extra="forbid")

    offer_id: str = Field(description="Client-facing offer identifier")
    strategy_type: str = Field(description="Offer strategy classification (e.g. BOUNDED_DISCOUNT, BUNDLED_ADDON)")
    product_ids: List[str] = Field(default_factory=list, description="Offered product identifiers")
    offered_price_paise: int = Field(ge=0, description="Customer-payable amount in integer paise")
    currency: str = Field(default="INR", description="Currency code")
    display_discount_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Customer-visible discount percentage")
    positioning: Optional[str] = Field(default=None, description="Commercial framing/headline for buyer")
    rationale: str = Field(description="Explainable customer-visible value proposition")


class MerchantEvaluationView(BaseModel):
    """Confidential merchant-internal decision science and financial evaluation.

    STRICT PRIVACY INVARIANT:
    For internal merchant analytics, lifecycle evaluation, and audit only.
    MUST NEVER be serialized to buyer-facing clients.
    """
    model_config = ConfigDict(extra="forbid")

    selected_policy_id: str
    strategy_type: str
    proposed_price_paise: int
    cogs_paise: int = Field(ge=0, description="Unit cost of goods sold in paise")
    gross_profit_paise: int = Field(description="net_revenue - cogs in paise")
    gross_margin_percent: float = Field(description="Gross margin percentage")
    discount_percent: float = Field(default=0.0, description="Effective discount percentage")
    predicted_contribution_paise: int = Field(description="Model predicted contribution in paise")
    uncertainty: float = Field(ge=0.0, description="Predictive uncertainty from LinUCB")
    ucb_score_paise: int = Field(description="Exploration diagnostic score")
    composite_ranking_score: float = Field(ge=0.0, le=1.0, description="Multi-factor ranking score")


class DecisionPolicyView(BaseModel):
    """Canonical policy candidate view (contains full decision telemetry)."""
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    strategy_type: str
    product_ids: List[str] = Field(default_factory=list)
    proposed_price_paise: int = Field(ge=0)
    gross_profit_paise: int = 0
    gross_margin_percent: float = 0.0
    discount_percent: float = 0.0
    rationale: str
    economics: Optional[Dict[str, Any]] = None


class DecisionScores(BaseModel):
    """Quantitative scoring details for explainability."""
    model_config = ConfigDict(extra="forbid")

    predicted_contribution_paise: int
    uncertainty: float = Field(ge=0.0)
    ucb_score_paise: int
    composite_ranking_score: float = Field(ge=0.0, le=1.0)


class ExplorationSafetyTrace(BaseModel):
    """Telemetry from Phase 8.7 exploration safety validation.

    CRITICAL BOUNDARY INVARIANT:
    This trace records point-in-time exploration safety check results from Phase 8.7.
    It does NOT constitute runtime execution authorization, which is strictly
    deferred to Phase 9.2 (Execution Gate).
    """
    model_config = ConfigDict(extra="forbid")

    safety_check_id: Optional[str] = None
    status: str = "ADMISSIBLE"
    is_admissible: bool = True
    rejection_reasons: List[str] = Field(default_factory=list)
    margin_floor_evaluated: bool = True
    discount_ceiling_evaluated: bool = True
    inventory_evaluated: bool = True
    is_execution_authorized: bool = Field(
        default=False,
        description="Always False in Phase 9.1. Execution authorization requires Phase 9.2."
    )


# Alias for backward-compatibility with tests expecting DecisionSafetyAudit
DecisionSafetyAudit = ExplorationSafetyTrace


class DecisionModelMetadata(BaseModel):
    """Metadata regarding the learned model powering inference."""
    model_config = ConfigDict(extra="forbid")

    model_version: str
    observation_count: int = Field(ge=0)
    feature_dimension: int = Field(ge=1)
    alpha_paise: int = Field(ge=0)


class DecisionTrace(BaseModel):
    """Latency and execution tracing across the sequential pipeline."""
    model_config = ConfigDict(extra="forbid")

    intent_extraction_ms: float = 0.0
    commerce_context_ms: float = 0.0
    candidate_generation_ms: float = 0.0
    learned_prediction_ms: float = 0.0
    candidate_selection_ms: float = 0.0
    exploration_decision_ms: float = 0.0
    safety_validation_ms: float = 0.0
    total_latency_ms: float = 0.0
    candidates_generated_count: int = 0
    candidates_eligible_count: int = 0


CANONICAL_MERCHANT_DEMO_PROMPTS: Dict[str, str] = {
    "merch_atlas_travel": "High quality travel backpack for weekend travel under 7500",
    "merch_alpha": "Need high quality ultralight alpine expedition travel backpack under 15000",
    "merch_95_alpha": "High quality wireless noise cancelling headphones under 20000",
}


class CanonicalDecisionRequest(BaseModel):
    """Canonical shopping opportunity decision request."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(..., min_length=1, description="Tenant merchant identifier")
    request_id: Optional[str] = Field(default=None, description="Client transport request correlation ID")
    opportunity_id: Optional[str] = Field(default=None, description="Commercial opportunity identity (auto-generated if omitted)")
    buyer_intent: Optional[BuyerIntent] = Field(default=None, description="Structured buyer intent if already extracted")
    raw_prompt: Optional[str] = Field(default=None, description="Raw buyer prompt/query text if intent needs extraction")
    exploration_config: Optional[MerchantExplorationConfig] = Field(default=None, description="Optional exploration overrides")
    idempotency_key: Optional[str] = Field(default=None, description="Client idempotency key")
    runtime_version: str = Field(default=CANONICAL_DECISION_SCHEMA_VERSION, description="Contract version")

    @model_validator(mode="after")
    def validate_buyer_input(self) -> "CanonicalDecisionRequest":
        if not self.buyer_intent and not (self.raw_prompt and self.raw_prompt.strip()):
            if self.merchant_id in CANONICAL_MERCHANT_DEMO_PROMPTS and (self.raw_prompt is None or self.raw_prompt == ""):
                self.raw_prompt = CANONICAL_MERCHANT_DEMO_PROMPTS[self.merchant_id]
            else:
                raise ValueError("Either 'buyer_intent' or non-empty 'raw_prompt' must be provided.")
        return self


class DecisionEnvelope(BaseModel):
    """Authoritative, typed, immutable output of the Canonical Decision Runtime.

    Contract: canonical-decision/v1

    ARCHITECTURAL BOUNDARY:
    Phase 9.1 computes the canonical decision.
    Execution authorization and transaction processing are strictly deferred to Phase 9.2.
    """
    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(..., description="Unique decision identifier (dec_...)")
    request_id: Optional[str] = Field(default=None, description="Client transport request correlation ID")
    merchant_id: str = Field(..., description="Tenant merchant ID")
    opportunity_id: str = Field(..., description="Opportunity ID")
    decision_version: str = Field(default=CANONICAL_DECISION_SCHEMA_VERSION)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    buyer_context_key: str = Field(..., description="Canonical buyer context key")
    intent_summary: IntentSummary = Field(..., description="Summary of parsed buyer requirements")

    # 1. Public Buyer-Facing View (Zero internal economic/cost leakage)
    buyer_offer: BuyerOfferView = Field(..., description="Customer-facing offer details (zero COGS/margin)")

    # 2. Private Merchant Evaluation View (Internal decision science & economics)
    merchant_evaluation: MerchantEvaluationView = Field(..., description="Merchant-internal financial evaluation")

    # 3. Decision Telemetry & Candidate Details
    selected_policy: DecisionPolicyView = Field(..., description="Final selected commercial policy")
    decision_mode: DecisionMode = Field(..., description="EXPLOIT or EXPLORE")
    decision_reason: str = Field(..., description="Machine-readable decision rationale")
    scores: DecisionScores = Field(..., description="Predicted contribution and uncertainty")
    safety_audit: ExplorationSafetyTrace = Field(..., description="Phase 8.7 exploration safety telemetry")
    model_metadata: DecisionModelMetadata = Field(..., description="Learned model state snapshot")
    trace: DecisionTrace = Field(..., description="Execution performance and latency breakdown")

    # 4. Phase 9.2 Execution Boundary Demarcation
    execution_status: str = Field(
        default="PENDING_EXECUTION_GATE",
        description="Execution status. In Phase 9.1, always PENDING_EXECUTION_GATE. Phase 9.2 gate required."
    )
    execution_authorized: bool = Field(
        default=False,
        description="Strictly False in Phase 9.1. Execution authorization cannot be granted by 9.1 decision runtime."
    )
