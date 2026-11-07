"""Pydantic v2 Schemas and DTOs for Phase 10 Merchant AI Control Center.

Contract: dashboard-view/v1

Enforces:
1. Strict read/projection separation (zero raw database models or LinUCB matrices).
2. Strict information hygiene: Buyer-facing views contain ZERO merchant economics (COGS, margins).
3. Explicit evidence semantics: Distinguishes EXPECTED, OBSERVED, and TEST_MODE_OBSERVED.
4. All models enforce ConfigDict(extra="forbid").
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class RuntimeHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    ATTENTION_REQUIRED = "ATTENTION_REQUIRED"


class EvidenceClass(str, Enum):
    SIMULATED = "SIMULATED"
    TEST_MODE_OBSERVED = "TEST_MODE_OBSERVED"
    OBSERVED = "OBSERVED"


class AttentionSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# =============================================================================
# 1. OVERVIEW DTOs
# =============================================================================

class AttentionItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    severity: AttentionSeverity
    title: str
    description: str
    entity_id: Optional[str] = None
    count: int = 1
    timestamp: datetime
    action_hint: Optional[str] = None


class ActivePolicySummaryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    policy_version: str
    strategy_type: str
    lifecycle_status: str
    observed_contribution_paise: int = 0
    evidence_count: int = 0
    context_coverage_count: int = 0
    promoted_at: Optional[datetime] = None


class LearningInsightDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    buyer_context_key: str
    context_description: str
    observed_preference_strategy: str
    evidence_count: int
    context_coverage_count: int
    observed_contribution_paise: int
    evidence_strength: str  # e.g., "HIGH", "MODERATE", "COLD_START"
    evidence_class: EvidenceClass = EvidenceClass.TEST_MODE_OBSERVED


class RecentDecisionItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    opportunity_id: str
    created_at: datetime
    buyer_context_key: str
    selected_strategy_type: str
    proposed_price_paise: int
    decision_mode: str  # EXPLOIT / EXPLORE
    execution_status: str  # PENDING_EXECUTION_GATE / EXECUTION_COMPLETED / SAFETY_REJECTED
    outcome_status: Optional[str] = None  # PAYMENT_SUCCESS / ORDER_CREATED / etc.
    learning_eligible: bool = False


class DashboardOverviewDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    merchant_name: str
    currency: str
    runtime_status: RuntimeHealthStatus
    status_headline: str
    status_subtext: str

    # Key Performance Indicators
    ai_buyer_opportunities_count: int = 0
    decision_count: int = 0
    authorized_executions_count: int = 0
    paid_transactions_count: int = 0
    expected_contribution_paise: int = 0
    observed_contribution_paise: int = 0
    test_mode_observed_contribution_paise: int = 0
    decision_rate_percent: float = 100.0
    total_learning_observations_count: int = 0
    total_contexts_count: int = 0

    # Section Panels
    active_policy: Optional[ActivePolicySummaryDTO] = None
    learning_insight: Optional[LearningInsightDTO] = None
    attention_items: List[AttentionItemDTO] = Field(default_factory=list)
    recent_decisions: List[RecentDecisionItemDTO] = Field(default_factory=list)
    generated_at: datetime


# =============================================================================
# 2. AI DECISIONS DTOs
# =============================================================================

class DecisionBuyerOfferViewDTO(BaseModel):
    """Customer/Buyer facing view — ZERO internal economic or cost leakage."""
    model_config = ConfigDict(extra="forbid")

    offer_title: str
    product_ids: List[str] = Field(default_factory=list)
    offer_price_paise: int
    currency: str = "INR"
    strategy_type: str
    warranty_months: int = 0
    delivery_days: int = 2
    included_items: List[str] = Field(default_factory=list)


class DecisionMerchantEvaluationDTO(BaseModel):
    """Merchant internal financial evaluation — private decision science."""
    model_config = ConfigDict(extra="forbid")

    cogs_paise: int
    gross_profit_paise: int
    gross_margin_percent: float
    predicted_contribution_paise: int
    uncertainty: float
    composite_ranking_score: float
    decision_mode: str  # EXPLOIT / EXPLORE
    rationale: str


class DecisionCandidateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    strategy_type: str
    proposed_price_paise: int
    predicted_contribution_paise: int
    uncertainty: float
    composite_ranking_score: float
    is_selected: bool


class IntentSummaryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Optional[str] = "General"
    use_case: Optional[str] = None
    quantity: Optional[int] = 1
    budget_paise: Optional[int] = None
    hard_requirements: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)
    raw_prompt: Optional[str] = None


class DecisionDetailDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    request_id: Optional[str] = None
    merchant_id: str
    opportunity_id: str
    buyer_context_key: str
    created_at: datetime
    raw_prompt: Optional[str] = None
    intent_summary: Optional[IntentSummaryDTO] = None

    # Complete Identity Trace Chain
    authorization_id: Optional[str] = None
    execution_id: Optional[str] = None
    order_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    authorized_amount_paise: Optional[int] = None
    payment_id: Optional[str] = None
    outcome_id: Optional[str] = None
    evidence_id: Optional[str] = None
    memory_id: Optional[str] = None
    applied_observation_id: Optional[str] = None

    # Strict Dual Views
    buyer_offer: DecisionBuyerOfferViewDTO
    merchant_evaluation: DecisionMerchantEvaluationDTO

    # Candidates & Selection
    candidates: List[DecisionCandidateDTO] = Field(default_factory=list)

    # Safety & Gate Status
    safety_status: str
    safety_rejection_reasons: List[str] = Field(default_factory=list)
    execution_status: str
    transaction_state: Optional[str] = None
    outcome_status: Optional[str] = None
    learning_eligible: bool = False
    reward_contribution_paise: Optional[int] = None


class DecisionListResponseDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[RecentDecisionItemDTO]
    total: int
    limit: int
    offset: int


# =============================================================================
# 3. POLICIES DTOs
# =============================================================================

class PolicyVersionItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    version_id: str
    strategy_type: str
    lifecycle_status: str  # CANDIDATE, ACTIVE, RETIRED, ROLLED_BACK
    created_at: datetime
    promoted_at: Optional[datetime] = None
    evidence_count: int = 0
    observed_contribution_paise: int = 0
    promotion_criteria_satisfied: bool = False
    is_active: bool = False


class PolicyTransitionItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transition_id: str
    policy_id: str
    from_state: str
    to_state: str
    action: str  # PROMOTED / ROLLED_BACK / RETIRED
    reason: str
    timestamp: datetime
    performed_by: str


class PolicyManagementDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    active_policy: Optional[ActivePolicySummaryDTO] = None
    versions: List[PolicyVersionItemDTO] = Field(default_factory=list)
    recent_transitions: List[PolicyTransitionItemDTO] = Field(default_factory=list)


# =============================================================================
# 4. EXPERIMENTS DTOs
# =============================================================================

class ExperimentItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    name: str
    status: str  # DRAFT, RUNNING, COMPLETED, STOPPED
    source: EvidenceClass = EvidenceClass.TEST_MODE_OBSERVED
    control_policy_id: str
    treatment_policy_id: str
    population_size: int
    control_observed_ecps_paise: Optional[int] = None
    treatment_observed_ecps_paise: Optional[int] = None
    observed_diff_paise: Optional[int] = None
    guardrail_status: str = "PASSED"
    created_at: datetime
    completed_at: Optional[datetime] = None


class ExperimentListResponseDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[ExperimentItemDTO]
    total: int


# =============================================================================
# 5. LEARNING DTOs
# =============================================================================

class LearningHealthDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eligible_opportunities_count: int = 0
    valid_evidence_count: int = 0
    rejected_evidence_count: int = 0
    memory_observations_count: int = 0
    model_updates_count: int = 0
    duplicate_observations_count: int = 0


class ContextLearningItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    buyer_context_key: str
    context_label: str
    preferred_strategy: str
    evidence_count: int
    observed_contribution_paise: int
    last_updated_at: datetime
    status: str = "ACTIVE_LEARNING"


class LearningModelMetadataDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_version: str
    algorithm_version: str
    feature_version: str
    dimension: int
    lambda_reg: float
    alpha_paise: int
    observation_count: int
    version: int
    last_updated_at: datetime
    learning_status: str = "OPTIMIZING"


class LearningCenterDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    health: LearningHealthDTO
    context_breakdown: List[ContextLearningItemDTO] = Field(default_factory=list)
    model_metadata: LearningModelMetadataDTO
    evidence_class: EvidenceClass = EvidenceClass.TEST_MODE_OBSERVED


# =============================================================================
# 6. ACTIVITY & TRACE DTOs
# =============================================================================

class ActivityEventItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_event_id: str
    timestamp: datetime
    entity_type: str
    action: str
    opportunity_id: Optional[str] = None
    decision_id: Optional[str] = None
    execution_id: Optional[str] = None
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ActivityListResponseDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[ActivityEventItemDTO]
    total: int
    limit: int
    offset: int


# =============================================================================
# 7. CONTROL ACTIONS DTOs
# =============================================================================

class PolicyPromoteActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    candidate_policy_id: str
    expected_previous_policy_id: Optional[str] = Field(default=None, description="Expected currently active policy ID for optimistic concurrency")
    rationale: str = Field(default="Merchant manual promotion via Control Center")


class PolicyRollbackActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    target_policy_id: str
    expected_current_policy_id: Optional[str] = Field(default=None, description="Expected currently active policy ID for optimistic concurrency")
    rationale: str = Field(default="Merchant safety rollback via Control Center")


class ControlActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    action: str
    policy_id: str
    message: str
    audit_event_id: Optional[str] = None
    timestamp: datetime
