"""Pydantic v2 Schemas and Contracts for Phase 8.1 Merchant Policy Learning Evidence.

Contracts:
- merchant-learning/v1
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from services.experiments.schemas import VariantType


# =============================================================================
# ENUMS
# =============================================================================

class EvidenceSource(str, Enum):
    """Source provenance taxonomy of an experimental or observational datum."""
    SIMULATED = "SIMULATED"
    TEST_MODE_OBSERVED = "TEST_MODE_OBSERVED"
    PRODUCTION_OBSERVED = "PRODUCTION_OBSERVED"  # Explicitly defined but unsupported in current track


class LearningOutcomeType(str, Enum):
    """Outcome taxonomy distinguishing simulated preference from verified payment."""
    SIMULATED_SELECTION = "SIMULATED_SELECTION"
    NO_SELECTION = "NO_SELECTION"
    ORDER_CREATED = "ORDER_CREATED"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILURE = "PAYMENT_FAILURE"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"
    EXPERIMENT_INCONCLUSIVE = "EXPERIMENT_INCONCLUSIVE"


class EvidenceQualityStatus(str, Enum):
    """Evidence quality classification reflecting experimental integrity."""
    VALID = "VALID"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    INCONCLUSIVE = "INCONCLUSIVE"
    GUARDRAIL_FAILURE = "GUARDRAIL_FAILURE"
    INVALID = "INVALID"


class EvidenceLifecycleState(str, Enum):
    """State machine governing evidence validity and consumption."""
    CAPTURED = "CAPTURED"
    VALIDATED = "VALIDATED"
    LEARNING_ELIGIBLE = "LEARNING_ELIGIBLE"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


# =============================================================================
# BUYER CONTEXT DIMENSIONS & KEYS
# =============================================================================

class BuyerContextDimensions(BaseModel):
    """Normalized, non-demographic commercial intent dimensions."""
    model_config = ConfigDict(extra="forbid")

    category: str = Field(..., description="Normalized product category (e.g. travel_backpack)")
    budget_tier: str = Field(..., description="Categorical budget tier (e.g. BUDGET_MID_3K_5K)")
    hard_requirement_signature: str = Field(
        ...,
        description="Sorted canonical string of hard constraints (e.g. laptop_size:gte:15.6|water_resistant:eq:True)"
    )
    preference_signature: str = Field(
        default="",
        description="Sorted canonical string of soft preferences (e.g. warranty:long_warranty)"
    )
    exclusion_signature: str = Field(
        default="",
        description="Sorted canonical string of exclusions (e.g. material:leather)"
    )


# =============================================================================
# PRIMARY CONTRACT: PolicyLearningEvidence (merchant-learning/v1)
# =============================================================================

class EvidenceGuardrailSummary(BaseModel):
    """Guardrail compliance record attached to learning evidence."""
    model_config = ConfigDict(extra="forbid")

    guardrail_type: str
    threshold_value: float
    observed_value: float
    passed: bool
    detail: str


class PolicyLearningEvidence(BaseModel):
    """Authoritative evidence record adhering to contract merchant-learning/v1.
    
    This contract serves as the strict firewall between experimentation
    and autonomous commercial policy learning.
    """
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(..., description="Unique evidence identifier (evi_...)")
    evidence_version: str = Field(default="merchant-learning/v1", description="Contract version")
    merchant_id: str = Field(..., description="Merchant tenant scoping identifier")

    # Experiment Provenance
    experiment_id: str = Field(..., description="Originating Phase 7 experiment ID")
    experiment_version: str = Field(default="policy-experiment/v1")
    experiment_observation_id: str = Field(..., description="Originating observation record ID")
    scenario_id: str = Field(..., description="Scenario opportunity identifier")

    # Policy Identity
    policy_id: str = Field(..., description="Target policy proposal ID")
    policy_version: str = Field(default="merchant-policy/v1")
    variant: VariantType = Field(..., description="Experimental arm (CONTROL or TREATMENT)")

    # Buyer Context Scoping (Zero PII, Zero Demographics)
    buyer_context_key: str = Field(
        ...,
        description="Deterministic hash of commercial intent dimensions (e.g. bck_travel_pack_tier2_...)"
    )
    buyer_intent_version: str = Field(default="buyer-intent/v1")

    # Simulation & Execution Provenance
    buyer_selection_result_id: Optional[str] = None
    simulation_version: Optional[str] = "buyer-selection/v1"
    execution_id: Optional[str] = None
    provider_order_id: Optional[str] = None  # Razorpay order ID (if Test Mode order created)
    verified_payment_id: Optional[str] = None # Razorpay payment ID (if webhook verified)

    # Source & Outcome Classifications
    source: EvidenceSource = Field(..., description="SIMULATED or TEST_MODE_OBSERVED")
    outcome_type: LearningOutcomeType = Field(..., description="Granular outcome class")
    sample_size: int = Field(default=1, description="Number of decision instances represented")
    is_selected: bool = Field(..., description="True if merchant offer was selected")

    # Strict Separation of Expected vs. Observed Economics (Paise & Decimals)
    expected_revenue_paise: int = Field(default=0, description="Model-expected revenue in integer paise")
    expected_contribution_paise: int = Field(default=0, description="Model-expected contribution in integer paise")
    observed_revenue_paise: Optional[int] = Field(
        default=None,
        description="Verified transaction revenue in integer paise (None if not executed/paid)"
    )
    observed_contribution_paise: Optional[int] = Field(
        default=None,
        description="Verified transaction contribution in integer paise (None if not executed/paid)"
    )
    margin_percent: float = Field(default=0.0, description="Gross profit margin percentage")

    # Guardrails & Evidence Quality
    guardrail_results: List[EvidenceGuardrailSummary] = Field(default_factory=list)
    evidence_status: EvidenceQualityStatus = Field(..., description="VALID, INSUFFICIENT_SAMPLE, etc.")
    lifecycle_state: EvidenceLifecycleState = Field(default=EvidenceLifecycleState.CAPTURED)

    # Deterministic Learning Eligibility (Server-Derived Only)
    learning_eligible: bool = Field(
        ...,
        description="True only if evidence passes all integrity, provenance, and quality checks"
    )
    eligibility_reasons: List[str] = Field(
        default_factory=list,
        description="Audit trace explaining eligibility determination"
    )

    # Aggregation & Idempotency
    aggregation_key: str = Field(
        ...,
        description="Canonical key for grouping: merchant_id:buyer_context_key:policy_id:policy_version"
    )
    idempotency_key: str = Field(
        ...,
        description="Stable key preventing duplicate learning evidence ingestion"
    )

    # Temporal Audit
    observed_at: datetime = Field(..., description="Timestamp when outcome was originally observed")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when evidence was ingested")


# =============================================================================
# API REQUEST & QUERY MODELS
# =============================================================================

class IngestExperimentRequest(BaseModel):
    """Payload to ingest observations from a completed Phase 7 experiment."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    experiment_id: str
    force_reingest: bool = False


class EvidenceFilter(BaseModel):
    """Query filters for retrieving learning evidence."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    buyer_context_key: Optional[str] = None
    policy_id: Optional[str] = None
    learning_eligible_only: bool = True
    source: Optional[EvidenceSource] = None
    limit: int = 100
    offset: int = 0
