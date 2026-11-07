"""Pydantic v2 Schemas and Contracts for Phase 7 Controlled Policy Experiments.

Contracts:
- policy-experiment/v1
- experiment-result/v1
- experiment-observation/v1
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# ENUMS
# =============================================================================

class ExperimentStatus(str, Enum):
    """Lifecycle state machine for a controlled policy experiment."""
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INCONCLUSIVE = "INCONCLUSIVE"


class VariantType(str, Enum):
    """Experimental arm identifier."""
    CONTROL = "CONTROL"
    TREATMENT = "TREATMENT"


class OutcomeType(str, Enum):
    """Provenance class of an observed outcome."""
    SIMULATED = "SIMULATED"
    TEST_MODE_OBSERVED = "TEST_MODE_OBSERVED"


class EvidenceStatus(str, Enum):
    """Scientific evidence classification for an experiment result."""
    SUFFICIENT_EVIDENCE = "SUFFICIENT_EVIDENCE"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    INCONCLUSIVE = "INCONCLUSIVE"
    GUARDRAIL_FAILURE = "GUARDRAIL_FAILURE"
    NO_VALID_COMPARISON = "NO_VALID_COMPARISON"


class GuardrailType(str, Enum):
    """Constraint types that must not be violated by a winning treatment."""
    MIN_MARGIN_PERCENT = "MIN_MARGIN_PERCENT"
    MAX_DISCOUNT_PERCENT = "MAX_DISCOUNT_PERCENT"
    MAX_PRICE_PAISE = "MAX_PRICE_PAISE"
    INVENTORY_SAFETY = "INVENTORY_SAFETY"


class AssignmentStrategy(str, Enum):
    """Method used to allocate decision instances to experimental variants."""
    DETERMINISTIC_HASH = "DETERMINISTIC_HASH"
    PAIRED_COUNTERFACTUAL = "PAIRED_COUNTERFACTUAL"
    ROUND_ROBIN = "ROUND_ROBIN"


# =============================================================================
# EXPERIMENT DEFINITION & HYPOTHESIS
# =============================================================================

class ExperimentHypothesis(BaseModel):
    """Structured hypothesis establishing population, expected direction, and metrics."""
    model_config = ConfigDict(extra="forbid")

    population_description: str = Field(..., description="Target buyer or scenario population")
    control_description: str = Field(..., description="Baseline policy configuration")
    treatment_description: str = Field(..., description="Alternative policy being evaluated")
    expected_direction: str = Field(..., description="Expected delta direction (HIGHER or LOWER)")
    primary_metric: str = Field(..., description="North star metric evaluated (e.g. EXPECTED_CONTRIBUTION_PER_SHOPPER)")
    rationale: str = Field(..., description="Commercial rationale for the hypothesized effect")
    guardrail_metrics: List[str] = Field(default_factory=list, description="List of guardrails that must hold")


class ExperimentGuardrail(BaseModel):
    """Threshold rule that prevents declaring a winning variant if breached."""
    model_config = ConfigDict(extra="forbid")

    guardrail_type: GuardrailType
    threshold_value: float = Field(..., description="Numerical limit (e.g. 0.20 for 20% min margin)")
    description: str = Field(..., description="Human-readable guardrail explanation")


class PolicyDiff(BaseModel):
    """Deterministic structural and economic difference between Control and Treatment."""
    model_config = ConfigDict(extra="forbid")

    control_strategy: str
    treatment_strategy: str
    control_price_paise: int
    treatment_price_paise: int
    price_delta_paise: int
    control_margin_percent: float
    treatment_margin_percent: float
    margin_delta_percent: float
    control_included_items: List[str] = Field(default_factory=list)
    treatment_included_items: List[str] = Field(default_factory=list)
    added_items: List[str] = Field(default_factory=list)
    control_warranty_months: int = 0
    treatment_warranty_months: int = 0
    warranty_delta_months: int = 0
    treatment_incentives: List[str] = Field(default_factory=list)
    summary: str = Field(..., description="Summary of isolated policy diff")


class PolicyExperiment(BaseModel):
    """Controlled policy experiment definition adhering to contract policy-experiment/v1."""
    model_config = ConfigDict(extra="forbid")

    experiment_id: str = Field(..., description="Unique experiment identifier (exp_...)")
    experiment_version: str = Field(default="policy-experiment/v1", description="Contract version")
    merchant_id: str = Field(..., description="Merchant tenant identifier")
    name: str = Field(..., description="Human-readable experiment title")
    population_scenarios: List[str] = Field(default_factory=list, description="Target scenario IDs in population")
    control_policy_id: str = Field(..., description="Proposal ID of baseline policy")
    treatment_policy_id: str = Field(..., description="Proposal ID of alternative policy")
    control_proposal_snapshot: Dict[str, Any] = Field(..., description="Frozen snapshot of control proposal")
    treatment_proposal_snapshot: Dict[str, Any] = Field(..., description="Frozen snapshot of treatment proposal")
    policy_diff: Optional[PolicyDiff] = None
    hypothesis: ExperimentHypothesis
    primary_metric: str = Field(default="EXPECTED_CONTRIBUTION_PER_SHOPPER")
    secondary_metrics: List[str] = Field(
        default_factory=lambda: ["SELECTION_RATE", "AOV_PAISE", "MARGIN_PERCENT", "ORDER_CREATION_RATE"]
    )
    guardrails: List[ExperimentGuardrail] = Field(default_factory=list)
    randomization_seed: int = Field(default=42, description="Seed for deterministic SHA-256 assignment")
    assignment_strategy: AssignmentStrategy = AssignmentStrategy.DETERMINISTIC_HASH
    status: ExperimentStatus = ExperimentStatus.DRAFT
    sample_size_target: int = Field(default=50, description="Target evaluation opportunities")
    min_detectable_effect: float = Field(
        default=0.02,
        description="Minimum relative difference threshold (e.g. 0.02 for 2%) below which an effect is classified as INCONCLUSIVE"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(default="system")
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


# =============================================================================
# OBSERVATION CONTRACT (experiment-observation/v1)
# =============================================================================

class ExperimentObservation(BaseModel):
    """Audit record for a single decision instance under an experiment."""
    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(..., description="Unique observation identifier (obs_...)")
    experiment_id: str = Field(..., description="Associated experiment ID")
    scenario_id: str = Field(..., description="Target decision scenario ID")
    variant: VariantType = Field(..., description="Assigned experimental arm")
    outcome_type: OutcomeType = Field(default=OutcomeType.SIMULATED)
    buyer_selection_result_id: Optional[str] = None
    selected_offer_id: Optional[str] = None
    is_selected: bool = Field(..., description="True if merchant variant won the buyer choice")
    execution_id: Optional[str] = None
    order_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    payment_outcome: Optional[str] = None  # None, PENDING, AUTHORIZED, CAPTURED, FAILED
    revenue_paise: int = Field(default=0, description="Revenue in integer paise (0 if not selected)")
    contribution_paise: int = Field(default=0, description="Gross contribution in paise")
    margin_percent: float = Field(default=0.0)
    guardrail_violations: List[str] = Field(default_factory=list)
    observed_at: datetime = Field(default_factory=datetime.utcnow)
    idempotency_key: str = Field(..., description="Stable key preventing duplicate accounting")


# =============================================================================
# METRICS & RESULTS CONTRACT (experiment-result/v1)
# =============================================================================

class VariantMetrics(BaseModel):
    """Aggregated deterministic metrics for an experimental variant."""
    model_config = ConfigDict(extra="forbid")

    sample_size: int = 0
    selection_count: int = 0
    selection_rate: float = 0.0
    order_creation_count: int = 0
    order_creation_rate: float = 0.0
    payment_success_count: int = 0
    payment_success_rate: float = 0.0
    total_revenue_paise: int = 0
    aov_paise: int = 0
    total_contribution_paise: int = 0
    expected_contribution_per_shopper_paise: int = 0
    average_margin_percent: float = 0.0
    guardrail_violation_count: int = 0


class MetricDelta(BaseModel):
    """Comparative delta between Treatment and Control (Treatment - Control)."""
    model_config = ConfigDict(extra="forbid")

    metric_name: str
    control_value: float
    treatment_value: float
    absolute_difference: float
    relative_difference_percent: Optional[float] = None
    directionally_improved: bool


class GuardrailResult(BaseModel):
    """Outcome of evaluating a guardrail constraint against treatment metrics."""
    model_config = ConfigDict(extra="forbid")

    guardrail_type: GuardrailType
    threshold_value: float
    observed_value: float
    passed: bool
    detail: str


class ExperimentResult(BaseModel):
    """Definitive machine-readable experiment evaluation result."""
    model_config = ConfigDict(extra="forbid")

    result_version: str = Field(default="experiment-result/v1")
    experiment_id: str
    merchant_id: str
    status: ExperimentStatus
    evidence_status: EvidenceStatus
    winner: Optional[VariantType] = None
    winner_rationale: str
    sample_counts: Dict[str, int]
    actual_control_count: int = Field(default=0, description="Actual observed sample count assigned to Control")
    actual_treatment_count: int = Field(default=0, description="Actual observed sample count assigned to Treatment")
    allocation_ratio: float = Field(default=1.0, description="Observed treatment-to-control ratio (treatment_count / control_count)")
    control_metrics: VariantMetrics
    treatment_metrics: VariantMetrics
    metric_deltas: Dict[str, MetricDelta]
    guardrail_results: List[GuardrailResult]
    policy_diff: Optional[PolicyDiff] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# API REQUEST / RESPONSE MODELS
# =============================================================================

class CreateExperimentRequest(BaseModel):
    """Payload to create a new controlled policy experiment draft."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    name: str
    control_policy_id: str
    treatment_policy_id: str
    population_scenarios: List[str]
    hypothesis: ExperimentHypothesis
    primary_metric: str = "EXPECTED_CONTRIBUTION_PER_SHOPPER"
    secondary_metrics: List[str] = Field(
        default_factory=lambda: ["SELECTION_RATE", "AOV_PAISE", "MARGIN_PERCENT"]
    )
    guardrails: List[ExperimentGuardrail] = Field(default_factory=list)
    randomization_seed: int = 42
    assignment_strategy: AssignmentStrategy = AssignmentStrategy.DETERMINISTIC_HASH
    min_detectable_effect: float = 0.02


class StartExperimentRequest(BaseModel):
    """Payload to transition an experiment to RUNNING state."""
    model_config = ConfigDict(extra="forbid")

    force_revalidation: bool = False


class RunExperimentRequest(BaseModel):
    """Payload to execute the experiment across its assigned scenario population."""
    model_config = ConfigDict(extra="forbid")

    execute_test_mode_orders: bool = Field(
        default=False,
        description="If True, routes selected offers under each assigned variant through Phase 5 ExecutionGate into Razorpay Test Mode"
    )
    population_intents: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="Optional custom BuyerIntent payloads for population scenarios"
    )
