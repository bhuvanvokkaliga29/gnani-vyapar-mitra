"""Versioned schemas and contracts for Phase 8.3 Merchant Policy Memory.

Contract Version: merchant-memory/v1
Formula Version: contribution-formula/v1
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from services.experiments.schemas import VariantType
from services.learning.schemas import EvidenceSource, LearningOutcomeType
from services.reward.schemas import RewardState


class PolicyMemoryRecordSchema(BaseModel):
    """Authoritative memory representation of an immutable historical policy observation.
    
    Conforms to contract merchant-memory/v1.
    """
    model_config = ConfigDict(extra="forbid")

    memory_id: str = Field(..., description="Unique memory record ID (mem_...)")
    memory_version: str = Field(default="merchant-memory/v1", description="Contract version")
    merchant_id: str = Field(..., description="Merchant tenant ID")
    
    # Canonical Identities
    opportunity_id: str = Field(..., description="Canonical decision-instance ID: {experiment_id}:{scenario_id}:{variant}")
    buyer_context_key: str = Field(..., description="Deterministic commercial intent fingerprint")
    scenario_id: str = Field(..., description="Benchmark/simulation scenario ID")
    policy_id: str = Field(..., description="Target policy ID")
    policy_version: str = Field(default="merchant-policy/v1", description="Immutable policy version")
    experiment_id: str = Field(..., description="Experiment ID")
    experiment_version: str = Field(default="policy-experiment/v1")
    variant: VariantType = Field(..., description="CONTROL or TREATMENT")
    
    # Upstream Evidence & Provenance
    evidence_id: str = Field(..., description="Upstream Phase 8.1 PolicyLearningEvidence ID")
    evidence_source: EvidenceSource = Field(..., description="SIMULATED or TEST_MODE_OBSERVED")
    outcome_type: LearningOutcomeType = Field(..., description="Granular outcome type")
    learning_eligible: bool = Field(..., description="True if evidence passed Phase 8.1 eligibility firewall")
    
    # Authoritative Reward Facts (Phase 8.2)
    reward_id: str = Field(..., description="Upstream Phase 8.2 PolicyOpportunityReward ID")
    reward_version: str = Field(default="merchant-reward/v1")
    formula_version: str = Field(default="contribution-formula/v1")
    reward_state: RewardState = Field(..., description="Reward admissibility state")
    is_admissible: bool = Field(..., description="True if admissible in opportunity population denominator")
    is_safety_violation: bool = Field(default=False, description="True if opportunity breached commercial guardrails")
    
    # Financial Facts (Integer Paise & Decimal)
    realized_revenue_paise: int = Field(default=0, description="Realized transaction revenue in paise")
    realized_cogs_paise: int = Field(default=0, description="Realized variable COGS in paise")
    realized_discount_paise: int = Field(default=0, description="Merchant-funded promotional discount in paise")
    reward_contribution_paise: int = Field(default=0, description="Net modeled commercial contribution in paise")
    margin_percent: float = Field(default=0.0, description="Gross profit margin percentage")
    
    # Supersession & Reconciliation Lineage
    is_current: bool = Field(default=True, description="True if this is the current authoritative effective state")
    superseded_by: Optional[str] = Field(default=None, description="Memory ID of superseding record if corrected")
    supersedes: Optional[str] = Field(default=None, description="Memory ID of previous record this replaces")
    correction_reason: Optional[str] = Field(default=None, description="Reason for reconciliation or supersession")
    reconciliation_ref: Optional[str] = Field(default=None, description="Upstream transaction or webhook event reference")

    # Audit & Deduplication
    idempotency_key: str = Field(..., description="Deterministic deduplication key")
    observed_at: datetime = Field(..., description="Timestamp observation occurred")
    persisted_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp persisted to memory")


class HistoricalObservationFilter(BaseModel):
    """Filter parameters for deterministic historical query and retrieval."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(..., description="Merchant tenant ID (mandatory)")
    policy_id: Optional[str] = Field(default=None, description="Filter by policy ID")
    policy_version: Optional[str] = Field(default=None, description="Filter by exact policy version")
    buyer_context_key: Optional[str] = Field(default=None, description="Filter by commercial intent fingerprint")
    experiment_id: Optional[str] = Field(default=None, description="Filter by experiment ID")
    variant: Optional[VariantType] = Field(default=None, description="Filter by variant arm")
    evidence_source: Optional[EvidenceSource] = Field(default=None, description="Filter by source")
    learning_eligible_only: Optional[bool] = Field(default=None, description="If True, only return learning-eligible")
    is_admissible_only: Optional[bool] = Field(default=None, description="If True, only return population-admissible")
    is_current_only: Optional[bool] = Field(default=None, description="If True, only return current effective records; if False, superseded; if None, all")
    start_time: Optional[datetime] = Field(default=None, description="Earliest observation timestamp")
    end_time: Optional[datetime] = Field(default=None, description="Latest observation timestamp")
    limit: int = Field(default=50, ge=1, le=500, description="Pagination limit")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class HistoricalObservationList(BaseModel):
    """Paginated list response of historical policy observations."""
    model_config = ConfigDict(extra="forbid")

    total_count: int = Field(..., description="Total matching records in storage")
    limit: int = Field(..., description="Page limit")
    offset: int = Field(..., description="Page offset")
    items: List[PolicyMemoryRecordSchema] = Field(..., description="Deterministic list of observations")


class HistoricalPolicySummary(BaseModel):
    """Factual summary metrics for a policy under a specified context or merchant-wide.
    
    CRITICAL: Contains facts and aggregates ONLY. No recommendations, no winners, no decisions.
    """
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    policy_id: str
    policy_version: Optional[str] = None
    buyer_context_key: Optional[str] = None
    evaluation_view: str = Field(default="CURRENT_EFFECTIVE", description="View type: CURRENT_EFFECTIVE vs RAW_HISTORICAL")
    
    # Opportunity Counts
    total_opportunities: int = Field(default=0, description="Total opportunities presented")
    eligible_opportunities: int = Field(default=0, description="Eligible opportunities in denominator")
    ineligible_opportunities: int = Field(default=0, description="Ineligible or corrupted observations excluded")
    guardrail_violations: int = Field(default=0, description="Opportunities that breached safety guardrails")
    is_policy_admissible: bool = Field(default=True, description="True only if 0 guardrail violations occurred")
    
    # Conversion Funnel
    order_created_count: int = Field(default=0, description="Count of orders created")
    converted_payments: int = Field(default=0, description="Count of successful captured payments")
    conversion_rate: float = Field(default=0.0, description="converted_payments / eligible_opportunities")
    
    # Financial Aggregates
    total_realized_revenue_paise: int = Field(default=0, description="Sum of realized revenue across eligible opportunities")
    total_realized_cogs_paise: int = Field(default=0, description="Sum of realized COGS across eligible opportunities")
    total_contribution_paise: int = Field(default=0, description="Sum of modeled gross contribution")
    contribution_per_shopper_paise: int = Field(default=0, description="total_contribution_paise / eligible_opportunities (rounded)")
    contribution_per_shopper_decimal: float = Field(default=0.0, description="Exact floating division")
    average_margin_percent: float = Field(default=0.0, description="Weighted average margin percentage")
    
    # Temporal Bounds
    earliest_observed_at: Optional[datetime] = None
    latest_observed_at: Optional[datetime] = None


class RecordMemoryRequest(BaseModel):
    """API request payload to persist authoritative evidence into historical memory."""
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(..., description="Authoritative Phase 8.1 evidence ID")
    merchant_id: str = Field(..., description="Merchant tenant ID")
    correction_reason: Optional[str] = Field(default=None, description="Optional reconciliation/correction reason")
    reconciliation_ref: Optional[str] = Field(default=None, description="Optional upstream transaction/event reference")
