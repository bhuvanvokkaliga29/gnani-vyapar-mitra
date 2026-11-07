"""Pydantic v2 Schemas and Contracts for Phase 8.2 Learning Objective & Reward Layer.

Contracts:
- merchant-reward/v1
- contribution-formula/v1
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from services.experiments.schemas import VariantType
from services.learning.schemas import EvidenceSource, LearningOutcomeType, EvidenceQualityStatus


# =============================================================================
# ENUMS
# =============================================================================

class RewardState(str, Enum):
    """Deterministic admissibility and realization state of an opportunity reward."""
    REWARD_ELIGIBLE = "REWARD_ELIGIBLE"                         # Verified positive or negative financial contribution
    REWARD_ZERO = "REWARD_ZERO"                                 # Eligible non-purchase/non-conversion (0 contribution)
    REWARD_GUARDRAIL_VIOLATION = "REWARD_GUARDRAIL_VIOLATION"   # Safety violation (0 contribution, retained in denominator)
    REWARD_INELIGIBLE = "REWARD_INELIGIBLE"                     # Inadmissible due to corrupt or incomplete pipeline criteria
    REWARD_DATA_UNAVAILABLE = "REWARD_DATA_UNAVAILABLE"         # Missing required inputs
    REWARD_INVALID = "REWARD_INVALID"                           # Broken integrity or contradictory evidence


class ObjectiveMetricType(str, Enum):
    """Primary learning objective metric classification."""
    OBSERVED_CONTRIBUTION_PER_SHOPPER = "OBSERVED_CONTRIBUTION_PER_SHOPPER"
    EXPECTED_CONTRIBUTION_PER_SHOPPER = "EXPECTED_CONTRIBUTION_PER_SHOPPER"


# =============================================================================
# REWARD CONTRACTS (merchant-reward/v1)
# =============================================================================

class PolicyOpportunityReward(BaseModel):
    """Authoritative reward signal for an individual AI-buyer opportunity.
    
    Adheres to contract merchant-reward/v1.
    """
    model_config = ConfigDict(extra="forbid")

    reward_id: str = Field(..., description="Unique reward record ID (rwd_...)")
    reward_version: str = Field(default="merchant-reward/v1", description="Reward contract version")
    formula_version: str = Field(default="contribution-formula/v1", description="Economic formula version")
    merchant_id: str = Field(..., description="Merchant tenant scoping ID")

    # Opportunity Identity (Optimization Unit)
    opportunity_id: str = Field(
        ...,
        description="Authoritative opportunity identifier: {experiment_id}:{scenario_id}:{variant}"
    )
    buyer_context_key: str = Field(..., description="Normalized commercial intent key")
    policy_id: str = Field(..., description="Evaluated policy proposal ID")
    policy_version: str = Field(default="merchant-policy/v1")
    experiment_id: str = Field(..., description="Originating experiment ID")
    experiment_version: str = Field(default="policy-experiment/v1")
    variant: VariantType = Field(..., description="CONTROL or TREATMENT")

    # Provenance Linkage
    evidence_id: str = Field(..., description="Originating Phase 8.1 PolicyLearningEvidence ID")
    evidence_source: EvidenceSource = Field(..., description="SIMULATED or TEST_MODE_OBSERVED")
    outcome_type: LearningOutcomeType = Field(..., description="Granular outcome type")

    # Admissibility & Reward State
    reward_state: RewardState = Field(..., description="Admissibility classification")
    is_admissible: bool = Field(
        ...,
        description="True if reward is admissible for objective population denominator (REWARD_ELIGIBLE, REWARD_ZERO, REWARD_GUARDRAIL_VIOLATION)"
    )
    is_safety_violation: bool = Field(
        default=False,
        description="True if opportunity suffered a guardrail or commercial safety failure"
    )
    inadmissibility_reasons: List[str] = Field(default_factory=list, description="Reason for inadmissibility or violation")

    # Authoritative Economic Values (Exact Integer Paise & Decimal)
    realized_revenue_paise: int = Field(default=0, description="Realized transaction revenue in paise")
    realized_cogs_paise: int = Field(default=0, description="Realized variable COGS in paise")
    realized_discount_paise: int = Field(default=0, description="Merchant-funded promotional discount in paise")
    reward_contribution_paise: int = Field(
        default=0,
        description="Net economic contribution in paise (can be negative if selling below COGS)"
    )
    margin_percent: float = Field(default=0.0, description="Gross profit margin percentage")

    # Temporal & Audit Metadata
    idempotency_key: str = Field(..., description="Deterministic key preventing duplicate reward accounting")
    evaluated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp reward was evaluated")


class AggregatedRewardObjective(BaseModel):
    """Authoritative aggregated learning objective over an eligible opportunity population.
    
    Adheres to contract merchant-reward/v1.
    """
    model_config = ConfigDict(extra="forbid")

    objective_id: str = Field(..., description="Unique objective calculation ID (obj_...)")
    objective_version: str = Field(default="merchant-reward/v1", description="Contract version")
    formula_version: str = Field(default="contribution-formula/v1", description="Formula version")
    merchant_id: str = Field(..., description="Merchant tenant identifier")
    policy_id: str = Field(..., description="Target policy ID")
    policy_version: str = Field(default="merchant-policy/v1")
    buyer_context_key: Optional[str] = Field(default=None, description="Scoped context key if filtered")
    experiment_id: Optional[str] = Field(default=None, description="Scoped experiment ID if filtered")
    variant: Optional[VariantType] = Field(default=None, description="Scoped variant if filtered")

    metric_type: ObjectiveMetricType = Field(
        default=ObjectiveMetricType.OBSERVED_CONTRIBUTION_PER_SHOPPER,
        description="Primary objective classification"
    )

    # Opportunity Population & Denominator
    total_opportunities_evaluated: int = Field(
        ...,
        description="Total raw opportunities presented in population"
    )
    eligible_opportunity_count: int = Field(
        ...,
        description="THE DENOMINATOR: Count of eligible opportunities admissible for learning"
    )
    ineligible_opportunity_count: int = Field(
        default=0,
        description="Count of opportunities excluded due to guardrails or invalid evidence"
    )

    # Secondary Funnel Counts
    order_created_count: int = Field(default=0, description="Count of orders created")
    successful_payment_count: int = Field(default=0, description="Count of verified captured payments")
    successful_payment_rate: float = Field(
        default=0.0,
        description="Conversion rate: successful_payment_count / eligible_opportunity_count"
    )
    guardrail_violation_count: int = Field(
        default=0,
        description="Count of opportunities that suffered commercial guardrail breaches"
    )
    is_policy_admissible: bool = Field(
        default=True,
        description="True only if zero guardrail violations occurred (policy satisfies all commercial safety constraints)"
    )

    # Aggregate Economics
    total_realized_revenue_paise: int = Field(default=0, description="Sum of realized revenue across eligible opportunities")
    total_realized_cogs_paise: int = Field(default=0, description="Sum of realized COGS across eligible opportunities")
    total_realized_discount_paise: int = Field(default=0, description="Sum of discounts funded")
    total_contribution_paise: int = Field(
        default=0,
        description="THE NUMERATOR: Sum of contribution across all eligible opportunities"
    )

    # The Primary Learning Objective
    contribution_per_shopper_paise: int = Field(
        ...,
        description="Primary objective: total_contribution_paise / eligible_opportunity_count (rounded)"
    )
    contribution_per_shopper_decimal: float = Field(
        ...,
        description="Exact floating/decimal representation of contribution per shopper"
    )
    average_margin_percent: float = Field(default=0.0, description="Weighted gross margin across revenue")

    aggregation_key: str = Field(
        ...,
        description="Canonical key: merchant_id:buyer_context_key:policy_id:policy_version"
    )
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# API REQUEST & RESPONSE SCHEMAS
# =============================================================================

class RewardEvaluationRequest(BaseModel):
    """Request payload to evaluate an evidence record into an opportunity reward."""
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    merchant_id: str


class RewardAggregationRequest(BaseModel):
    """Request payload to aggregate rewards for a policy across an experiment or context."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    policy_id: str
    policy_version: str = "merchant-policy/v1"
    experiment_id: Optional[str] = None
    variant: Optional[VariantType] = None
    buyer_context_key: Optional[str] = None
