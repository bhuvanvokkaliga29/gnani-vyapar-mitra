"""Pydantic Schemas and Contracts for Phase 11.1 Canonical Benchmark Harness.

Contracts:
- benchmark-scenario/v1
- benchmark-result/v1
- benchmark-summary/v1

Enforces:
1. Strict typing and validation (extra="forbid").
2. Explicit separation of inputs from expectations.
3. Explicit expectation categories (exact, state, invariant, relational, no-side-effect,
   monotonicity, isolation, conservation).
4. Explicit failure classification (business, state mismatch, security, tenant isolation,
   economic, temporal, safety, learning, lifecycle, infrastructure, harness).
5. Information hygiene: No secret leakage, credentials, or private headers.
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

BENCHMARK_SCENARIO_VERSION = "benchmark-scenario/v1"
BENCHMARK_RESULT_VERSION = "benchmark-result/v1"
BENCHMARK_SUMMARY_VERSION = "benchmark-summary/v1"


class ScenarioCategory(str, Enum):
    """Categorization of benchmark scenarios for targeted selection and analysis."""
    DECISION = "DECISION"
    ECONOMICS = "ECONOMICS"
    SAFETY = "SAFETY"
    EXPLORATION = "EXPLORATION"
    EXECUTION = "EXECUTION"
    OUTCOME = "OUTCOME"
    LEARNING = "LEARNING"
    TEMPORAL = "TEMPORAL"
    LIFECYCLE = "LIFECYCLE"
    TENANT = "TENANT"
    SECURITY = "SECURITY"
    EXPERIMENT = "EXPERIMENT"
    RESILIENCE = "RESILIENCE"
    CONCURRENCY = "CONCURRENCY"
    AUTHORIZATION = "AUTHORIZATION"
    RECOVERY = "RECOVERY"


class BenchmarkStatus(str, Enum):
    """Outcome status of a scenario execution."""
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class FailureClass(str, Enum):
    """Structured failure classifications to distinguish root cause domains."""
    BUSINESS_INVARIANT_FAILURE = "BUSINESS_INVARIANT_FAILURE"
    EXPECTED_STATE_MISMATCH = "EXPECTED_STATE_MISMATCH"
    SECURITY_FAILURE = "SECURITY_FAILURE"
    TENANT_ISOLATION_FAILURE = "TENANT_ISOLATION_FAILURE"
    ECONOMIC_INTEGRITY_FAILURE = "ECONOMIC_INTEGRITY_FAILURE"
    TEMPORAL_INTEGRITY_FAILURE = "TEMPORAL_INTEGRITY_FAILURE"
    SAFETY_FAILURE = "SAFETY_FAILURE"
    LEARNING_INTEGRITY_FAILURE = "LEARNING_INTEGRITY_FAILURE"
    LIFECYCLE_FAILURE = "LIFECYCLE_FAILURE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    HARNESS_FAILURE = "HARNESS_FAILURE"


class ExpectationType(str, Enum):
    """Types of verification assertions supported by the harness."""
    EXACT_VALUE = "EXACT_VALUE"
    EXACT_STATE = "EXACT_STATE"
    INVARIANT = "INVARIANT"
    RELATIONAL = "RELATIONAL"
    NO_SIDE_EFFECT = "NO_SIDE_EFFECT"
    MONOTONICITY = "MONOTONICITY"
    ISOLATION = "ISOLATION"
    CONSERVATION = "CONSERVATION"


class BenchmarkExecutionMode(str, Enum):
    """Execution depth for a scenario."""
    DECISION_ONLY = "DECISION_ONLY"
    FULL_CLOSED_LOOP = "FULL_CLOSED_LOOP"
    EXECUTION_ONLY = "EXECUTION_ONLY"


class BenchmarkExpectation(BaseModel):
    """A single declarative expectation to assert against observed state."""
    model_config = ConfigDict(extra="forbid")

    expectation_id: str = Field(..., description="Unique assertion identifier")
    expectation_type: ExpectationType = Field(..., description="Assertion category")
    target_domain: str = Field(..., description="Observed domain (e.g. decision, boundary, outcome, learning, memory)")
    field_path: Optional[str] = Field(default=None, description="Dot-notated field path on observed state")
    operator: str = Field(default="eq", description="Comparison operator: eq, ne, gt, gte, lt, lte, in, is_none, is_not_none")
    expected_value: Any = Field(default=None, description="Expected value or reference value")
    failure_class: FailureClass = Field(default=FailureClass.BUSINESS_INVARIANT_FAILURE, description="Failure class if assertion fails")
    description: str = Field(..., description="Human-readable description of this requirement")


class InitialProductSpec(BaseModel):
    """Product specification for declarative scenario setup."""
    model_config = ConfigDict(extra="forbid")

    product_id: str
    name: str
    sku: str
    category: str
    price_paise: int
    cost_paise: int
    inventory_quantity: int = 20
    attributes: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class InitialMerchantSpec(BaseModel):
    """Merchant configuration for declarative scenario setup."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    name: str
    currency: str = "INR"
    status: str = "ACTIVE"
    business_objective: str = "BALANCE_REVENUE_AND_MARGIN"
    minimum_margin_percent: float = 15.0
    maximum_discount_percent: float = 25.0
    target_aov_paise: int = 500000


class InitialStateSpec(BaseModel):
    """Declarative initial state specification for test environment setup."""
    model_config = ConfigDict(extra="forbid")

    merchant: Optional[InitialMerchantSpec] = None
    products: List[InitialProductSpec] = Field(default_factory=list)
    active_policy_id: Optional[str] = None
    seed_memories: List[Dict[str, Any]] = Field(default_factory=list)


class BuyerContextInput(BaseModel):
    """Buyer prompt or intent provided as input to the scenario."""
    model_config = ConfigDict(extra="forbid")

    raw_prompt: Optional[str] = None
    buyer_intent: Optional[Dict[str, Any]] = None
    buyer_persona: Optional[str] = None


class ExpectedTerminalState(BaseModel):
    """High-level summary of expected terminal business state."""
    model_config = ConfigDict(extra="forbid")

    decision_mode: Optional[str] = None
    selected_strategy: Optional[str] = None
    execution_status: Optional[str] = None
    outcome_status: Optional[str] = None
    is_terminal: Optional[bool] = None
    learning_eligible: Optional[bool] = None
    reward_contribution_paise: Optional[int] = None
    active_policy_id: Optional[str] = None


class BenchmarkScenario(BaseModel):
    """Declarative scenario specification (benchmark-scenario/v1)."""
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(..., description="Unique scenario identifier")
    scenario_version: str = Field(default=BENCHMARK_SCENARIO_VERSION, description="Contract version")
    description: str = Field(..., description="Purpose and design of this benchmark test")
    category: ScenarioCategory = Field(..., description="Scenario category")
    merchant_id: str = Field(..., description="Tenant merchant scope")
    buyer_context: BuyerContextInput = Field(..., description="Buyer input context")
    initial_state: InitialStateSpec = Field(default_factory=InitialStateSpec, description="Initial database state setup")
    input_overrides: Dict[str, Any] = Field(default_factory=dict, description="Custom overrides passed to runtime")
    execution_mode: BenchmarkExecutionMode = Field(default=BenchmarkExecutionMode.FULL_CLOSED_LOOP, description="Pipeline depth")
    simulate_payment: bool = Field(default=True, description="Whether to simulate payment stage")
    payment_status_override: Optional[str] = Field(default=None, description="Optional override (captured, failed, cancelled)")
    expected_invariants: List[BenchmarkExpectation] = Field(default_factory=list, description="Declarative assertions")
    expected_terminal_state: Optional[ExpectedTerminalState] = Field(default=None, description="Summary terminal state")
    tags: List[str] = Field(default_factory=list, description="Searchable tags")
    seed: int = Field(default=42, description="Randomization seed for determinism")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary scenario metadata")


class ObservedStateSnapshot(BaseModel):
    """Sanitized observation of authoritative system state across the execution."""
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    opportunity_id: Optional[str] = None
    decision_id: Optional[str] = None
    decision_mode: Optional[str] = None
    selected_policy_id: Optional[str] = None
    selected_strategy: Optional[str] = None
    execution_authorized_9_1: bool = False
    offered_price_paise: Optional[int] = None
    execution_id: Optional[str] = None
    boundary_status: Optional[str] = None
    authorized_amount_paise: Optional[int] = None
    order_id: Optional[str] = None
    outcome_id: Optional[str] = None
    outcome_status: Optional[str] = None
    is_terminal: Optional[bool] = None
    learning_eligible: Optional[bool] = None
    reward_contribution_paise: Optional[int] = None
    evidence_id: Optional[str] = None
    memory_id: Optional[str] = None
    is_duplicate_execution: bool = False
    is_duplicate_outcome: bool = False
    model_observation_count: Optional[int] = None
    active_policy_id: Optional[str] = None
    audit_event_ids: List[str] = Field(default_factory=list)
    memory_count: int = 0
    total_observed_contribution_paise: int = 0
    promotion_status: Optional[str] = None
    promotion_failure_code: Optional[str] = None
    cross_tenant_rejected: Optional[bool] = None
    stale_state_rejected: Optional[bool] = None


class AssertionDiagnostic(BaseModel):
    """Detailed record of an individual assertion evaluation."""
    model_config = ConfigDict(extra="forbid")

    expectation_id: str
    expectation_type: ExpectationType
    passed: bool
    failure_class: Optional[FailureClass] = None
    target_domain: str
    field_path: Optional[str] = None
    expected: Any = None
    observed: Any = None
    message: str


class BenchmarkResult(BaseModel):
    """Canonical benchmark execution result (benchmark-result/v1)."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    scenario_id: str
    scenario_version: str = Field(default=BENCHMARK_RESULT_VERSION)
    started_at: datetime
    finished_at: datetime
    status: BenchmarkStatus
    category: ScenarioCategory
    merchant_id: str
    seed: int
    assertions_total: int
    assertions_passed: int
    assertions_failed: int
    observed_state: Optional[ObservedStateSnapshot] = None
    expected_state: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: List[AssertionDiagnostic] = Field(default_factory=list)
    artifacts: Dict[str, str] = Field(default_factory=dict)
    duration_ms: float


class BenchmarkSummary(BaseModel):
    """Canonical summary for a suite of scenario runs (benchmark-summary/v1)."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    summary_version: str = Field(default=BENCHMARK_SUMMARY_VERSION)
    started_at: datetime
    finished_at: datetime
    total_scenarios: int
    passed: int
    failed: int
    inconclusive: int
    assertions_total: int
    assertions_passed: int
    assertions_failed: int
    categories: Dict[str, int] = Field(default_factory=dict)
    duration_ms: float
    reproducibility_status: Optional[str] = None
