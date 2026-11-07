"""Typed Pydantic Schemas for Phase 8.8 Policy Lifecycle & Promotion Management.

Contracts:
- policy-lifecycle/v1
- promotion-policy/v1

Inviolable Invariants:
- PREDICTION ≠ PROMOTION; EXPLORATION ≠ PROMOTION; EXECUTION ≠ PROMOTION.
- Evidence-gated lifecycle transitions only.
- Single active policy version per merchant.
- Immutable policy version history.
- Fresh Phase 8.6 safety check clearance required for promotion and rollback.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

from services.policy.schemas import PolicyCandidate

LIFECYCLE_SCHEMA_VERSION = "policy-lifecycle/v1"
PROMOTION_CONFIG_VERSION = "promotion-policy/v1"


class PolicyLifecycleState(str, Enum):
    """Lifecycle state machine for a merchant commercial policy version."""
    CANDIDATE = "CANDIDATE"
    ELIGIBLE_FOR_PROMOTION = "ELIGIBLE_FOR_PROMOTION"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    ROLLED_BACK = "ROLLED_BACK"


class PromotionEvidenceType(str, Enum):
    """Authoritative classification of evidence supporting a promotion decision."""
    CONTROLLED_EXPERIMENT = "CONTROLLED_EXPERIMENT"
    OBSERVATIONAL_HISTORY = "OBSERVATIONAL_HISTORY"


class PromotionStatus(str, Enum):
    """Definitive lifecycle decision status."""
    PROMOTED = "PROMOTED"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    SAFETY_REJECTED = "SAFETY_REJECTED"
    CONFLICT = "CONFLICT"
    ROLLED_BACK = "ROLLED_BACK"
    INVALID = "INVALID"


class PromotionFailureCode(str, Enum):
    """Deterministic failure taxonomy for policy promotion & lifecycle transitions."""
    INSUFFICIENT_SAMPLE_SIZE = "INSUFFICIENT_SAMPLE_SIZE"
    NEGATIVE_CONTRIBUTION = "NEGATIVE_CONTRIBUTION"
    NO_IMPROVEMENT_OVER_BASELINE = "NO_IMPROVEMENT_OVER_BASELINE"
    GUARDRAIL_BREACH = "GUARDRAIL_BREACH"
    INCONCLUSIVE_EXPERIMENT = "INCONCLUSIVE_EXPERIMENT"
    EXPERIMENT_NOT_WON = "EXPERIMENT_NOT_WON"
    EXPERIMENT_NOT_FOUND = "EXPERIMENT_NOT_FOUND"
    EXPERIMENT_TREATMENT_MISMATCH = "EXPERIMENT_TREATMENT_MISMATCH"
    SAFETY_GATE_REJECTED = "SAFETY_GATE_REJECTED"
    PREDECESSOR_MISMATCH = "PREDECESSOR_MISMATCH"
    TARGET_VERSION_NOT_FOUND = "TARGET_VERSION_NOT_FOUND"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    CROSS_MERCHANT_FORBIDDEN = "CROSS_MERCHANT_FORBIDDEN"
    NO_OPPORTUNITY_EVIDENCE = "NO_OPPORTUNITY_EVIDENCE"
    ALREADY_ACTIVE = "ALREADY_ACTIVE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    FUTURE_EVIDENCE_REJECTED = "FUTURE_EVIDENCE_REJECTED"
    POLICY_VERSION_MISMATCH = "POLICY_VERSION_MISMATCH"
    OBSERVATIONAL_CONCENTRATION_EXCEEDED = "OBSERVATIONAL_CONCENTRATION_EXCEEDED"
    INSUFFICIENT_CONTEXT_DIVERSITY = "INSUFFICIENT_CONTEXT_DIVERSITY"
    OBSERVATIONAL_PROMOTION_DISALLOWED = "OBSERVATIONAL_PROMOTION_DISALLOWED"


class PromotionPolicyConfig(BaseModel):
    """Authoritative promotion criteria envelope conforming to promotion-policy/v1."""
    model_config = ConfigDict(extra="forbid")

    min_learning_opportunities: int = Field(default=20, ge=1, description="Minimum observed learning opportunities in memory for controlled experiment path")
    min_observational_learning_opportunities: Optional[int] = Field(default=None, ge=1, description="Minimum observed learning opportunities for observational path (defaults to min_learning_opportunities)")
    min_positive_contribution_paise: int = Field(default=1, ge=0, description="Minimum mean contribution paise required")
    min_improvement_over_baseline_paise: int = Field(default=0, description="Minimum improvement over baseline paise")
    require_controlled_experiment: bool = Field(default=False, description="Whether a valid Phase 7 experiment is mandatory")
    allow_observational_promotion: bool = Field(default=True, description="Whether observational evidence can promote a policy in absence of controlled experiment")
    max_tolerated_safety_violations: int = Field(default=0, ge=0, description="Maximum historical safety breaches tolerated")
    require_fresh_safety_check: bool = Field(default=True, description="Whether fresh Phase 8.6 safety check is mandatory")
    recency_window_days: int = Field(default=30, ge=1, description="Evidence lookback window in days")
    max_opportunity_contribution_share: float = Field(default=0.50, ge=0.0, le=1.0, description="Maximum fraction of total positive contribution from a single opportunity in observational path")
    min_distinct_contexts: int = Field(default=1, ge=1, description="Minimum distinct buyer context keys required for observational promotion")
    config_version: str = Field(default=PROMOTION_CONFIG_VERSION, description="Promotion criteria version")

    @property
    def effective_observational_min_sample(self) -> int:
        return self.min_observational_learning_opportunities if self.min_observational_learning_opportunities is not None else self.min_learning_opportunities


class PolicyPromotionRequest(BaseModel):
    """Caller request to evaluate and promote a candidate policy."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(min_length=1, max_length=64, description="Merchant tenant ID")
    candidate_policy_id: str = Field(min_length=1, max_length=64, description="Target policy ID to promote")
    candidate_policy_version: str = Field(default="merchant-policy/v1", description="Policy contract version")
    candidate_policy: Optional[PolicyCandidate] = Field(default=None, description="Optional full candidate definition")
    expected_previous_policy_id: Optional[str] = Field(default=None, description="Expected active predecessor for optimistic locking")
    expected_previous_policy_version: Optional[str] = Field(default=None, description="Expected active predecessor version")
    experiment_id: Optional[str] = Field(default=None, description="Phase 7 experiment reference if promoting from experiment")
    selection_id: Optional[str] = Field(default=None, description="Phase 8.5 selection reference")
    exploration_id: Optional[str] = Field(default=None, description="Phase 8.7 exploration reference")
    reason: str = Field(min_length=1, max_length=256, description="Business rationale for promotion")
    config: Optional[PromotionPolicyConfig] = Field(default=None, description="Optional promotion policy configuration")
    lifecycle_version: str = Field(default=LIFECYCLE_SCHEMA_VERSION, description="Lifecycle contract version")


class PolicyPromotionResult(BaseModel):
    """Authoritative outcome of an evidence-gated promotion evaluation."""
    model_config = ConfigDict(extra="forbid")

    promotion_id: str = Field(description="Unique promotion lifecycle record ID (prom_...)")
    merchant_id: str = Field(description="Merchant tenant ID")
    candidate_policy_id: str = Field(description="Candidate policy ID evaluated")
    candidate_policy_version: str = Field(description="Candidate policy version evaluated")
    previous_active_policy_id: Optional[str] = Field(default=None, description="Previous active policy ID if replaced")
    previous_active_policy_version: Optional[str] = Field(default=None, description="Previous active policy version if replaced")
    resulting_active_policy_id: Optional[str] = Field(default=None, description="Current active policy ID after evaluation")
    resulting_active_policy_version: Optional[str] = Field(default=None, description="Current active policy version after evaluation")
    promotion_status: PromotionStatus = Field(description="PROMOTED, NOT_ELIGIBLE, INSUFFICIENT_EVIDENCE, etc.")
    eligibility_status: str = Field(description="ELIGIBLE or INELIGIBLE with summary")
    failure_codes: List[PromotionFailureCode] = Field(default_factory=list, description="List of failure codes if promotion was denied")
    evidence_type: Optional[PromotionEvidenceType] = Field(default=None, description="CONTROLLED_EXPERIMENT or OBSERVATIONAL_HISTORY")
    observational_bias_warning: Optional[str] = Field(default=None, description="Explicit selection-bias warning when promoted on observational evidence")
    evidence_summary: Dict[str, Any] = Field(description="Snapshot of authoritative evidence metrics evaluated")
    safety_check_reference: Optional[str] = Field(default=None, description="Phase 8.6 safety check ID reference")
    promotion_config_version: str = Field(default=PROMOTION_CONFIG_VERSION, description="Promotion configuration version applied")
    lifecycle_version: str = Field(default=LIFECYCLE_SCHEMA_VERSION, description="Lifecycle contract version")
    created_at: datetime = Field(description="Timestamp of promotion evaluation")


class PolicyRollbackRequest(BaseModel):
    """Caller request to rollback merchant active policy to a historical version."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(min_length=1, max_length=64, description="Merchant tenant ID")
    target_policy_id: str = Field(min_length=1, max_length=64, description="Historical policy ID to reinstate")
    target_policy_version: str = Field(default="merchant-policy/v1", description="Historical policy version to reinstate")
    expected_current_policy_id: Optional[str] = Field(default=None, description="Expected currently active policy ID for optimistic concurrency")
    reason: str = Field(min_length=1, max_length=256, description="Business rationale for rollback")
    require_fresh_safety_check: bool = Field(default=True, description="Whether current Phase 8.6 safety check is required")
    lifecycle_version: str = Field(default=LIFECYCLE_SCHEMA_VERSION, description="Lifecycle contract version")


class PolicyRollbackResult(BaseModel):
    """Authoritative outcome of a policy rollback request."""
    model_config = ConfigDict(extra="forbid")

    rollback_id: str = Field(description="Unique rollback lifecycle record ID")
    merchant_id: str = Field(description="Merchant tenant ID")
    target_policy_id: str = Field(description="Reinstated policy ID")
    target_policy_version: str = Field(description="Reinstated policy version")
    previous_active_policy_id: str = Field(description="Deactivated policy ID")
    previous_active_policy_version: str = Field(description="Deactivated policy version")
    status: str = Field(description="ROLLED_BACK or REJECTED")
    failure_codes: List[PromotionFailureCode] = Field(default_factory=list, description="Failure codes if rollback denied")
    safety_check_reference: Optional[str] = Field(default=None, description="Phase 8.6 safety check reference")
    created_at: datetime = Field(description="Timestamp of rollback")


class ActivePolicyResponse(BaseModel):
    """Representation of the merchant's currently active policy."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(description="Merchant tenant ID")
    policy_id: str = Field(description="Authoritative active policy ID")
    policy_version: str = Field(description="Authoritative active policy version")
    policy: Optional[PolicyCandidate] = Field(default=None, description="Policy candidate payload if available")
    lifecycle_status: PolicyLifecycleState = Field(default=PolicyLifecycleState.ACTIVE, description="ACTIVE")
    activated_at: datetime = Field(description="Activation timestamp")
    promotion_id: Optional[str] = Field(default=None, description="Promotion decision reference")
