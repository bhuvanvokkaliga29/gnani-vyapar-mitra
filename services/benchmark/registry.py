"""Benchmark Scenario Registry and Canonical Smoke Scenarios for Phase 11.1.

Maintains a catalog of versioned benchmark scenarios and registers the minimal
canonical smoke validation set required by Phase 11.1:
1. SMOKE_HAPPY_PATH
2. SMOKE_PAYMENT_FAILURE
3. SMOKE_NO_OFFER
4. SMOKE_REPLAY_IDEMPOTENCY
"""

from typing import Dict, List, Optional
from services.benchmark.schemas import (
    BenchmarkScenario,
    ScenarioCategory,
    BenchmarkExecutionMode,
    BuyerContextInput,
    InitialStateSpec,
    InitialMerchantSpec,
    InitialProductSpec,
    ExpectedTerminalState,
    BenchmarkExpectation,
    ExpectationType,
    FailureClass,
)


class BenchmarkRegistry:
    """In-memory registry and discovery mechanism for benchmark scenarios."""

    _scenarios: Dict[str, BenchmarkScenario] = {}

    @classmethod
    def register(cls, scenario: BenchmarkScenario) -> None:
        """Register a scenario into the global catalog."""
        cls._scenarios[scenario.scenario_id] = scenario

    @classmethod
    def get(cls, scenario_id: str) -> Optional[BenchmarkScenario]:
        """Retrieve a registered scenario by ID."""
        return cls._scenarios.get(scenario_id)

    @classmethod
    def list_all(cls) -> List[BenchmarkScenario]:
        """List all currently registered scenarios."""
        return list(cls._scenarios.values())

    @classmethod
    def list_by_category(cls, category: ScenarioCategory) -> List[BenchmarkScenario]:
        """Filter registered scenarios by category."""
        return [s for s in cls._scenarios.values() if s.category == category]

    @classmethod
    def list_by_tag(cls, tag: str) -> List[BenchmarkScenario]:
        """Filter registered scenarios by tag."""
        return [s for s in cls._scenarios.values() if tag in s.tags]

    @classmethod
    def clear(cls) -> None:
        """Clear the scenario registry (useful for testing)."""
        cls._scenarios.clear()


# ==================== Canonical Smoke Scenarios ====================

def _create_smoke_merchant() -> InitialMerchantSpec:
    return InitialMerchantSpec(
        merchant_id="merch_bench_smoke",
        name="Smoke Benchmark Merchant",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=15.0,
        maximum_discount_percent=25.0,
        target_aov_paise=500000,
    )


def _create_smoke_products() -> List[InitialProductSpec]:
    return [
        InitialProductSpec(
            product_id="prod_smoke_bp_01",
            name="Smoke Trail Backpack 35L",
            sku="SKU-SMK-01",
            category="travel_backpack",
            price_paise=450000,
            cost_paise=250000,  # 44% margin
            inventory_quantity=25,
            attributes={"laptop_size": 15.6, "water_resistant": True},
            is_active=True,
        ),
        InitialProductSpec(
            product_id="prod_smoke_bp_02",
            name="Smoke City Commuter 20L",
            sku="SKU-SMK-02",
            category="travel_backpack",
            price_paise=300000,
            cost_paise=150000,  # 50% margin
            inventory_quantity=20,
            attributes={"laptop_size": 14.0, "water_resistant": False},
            is_active=True,
        ),
    ]


# 1. SMOKE_HAPPY_PATH
SCENARIO_SMOKE_HAPPY_PATH = BenchmarkScenario(
    scenario_id="SMOKE_HAPPY_PATH",
    description="End-to-end happy path: Valid buyer prompt, decision made, executed in test mode, payment captured, learning evidence recorded, memory updated.",
    category=ScenarioCategory.DECISION,
    merchant_id="merch_bench_smoke",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with 15.6 inch laptop compartment",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_smoke_merchant(),
        products=_create_smoke_products(),
        active_policy_id="cand_smoke_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="happy_exp_authorized_invariant",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="decision",
            field_path="execution_authorized_9_1",
            operator="eq",
            expected_value=False,
            failure_class=FailureClass.SAFETY_FAILURE,
            description="Phase 9.1 DecisionEnvelope must never grant runtime execution authority",
        ),
        BenchmarkExpectation(
            expectation_id="happy_exp_boundary_status",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="boundary",
            field_path="boundary_status",
            operator="eq",
            expected_value="EXECUTION_COMPLETED",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Phase 9.2 Boundary execution must complete successfully",
        ),
        BenchmarkExpectation(
            expectation_id="happy_exp_outcome_status",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="outcome",
            field_path="outcome_status",
            operator="eq",
            expected_value="PAYMENT_SUCCESS",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Phase 9.3 Outcome must resolve to PAYMENT_SUCCESS",
        ),
        BenchmarkExpectation(
            expectation_id="happy_exp_learning_eligible",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="outcome",
            field_path="learning_eligible",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
            description="Captured payment outcome must be learning-eligible",
        ),
        BenchmarkExpectation(
            expectation_id="happy_exp_reward_positive",
            expectation_type=ExpectationType.RELATIONAL,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="gt",
            expected_value=0,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Successful sale gross contribution reward must be strictly positive",
        ),
        BenchmarkExpectation(
            expectation_id="happy_exp_memory_recorded",
            expectation_type=ExpectationType.RELATIONAL,
            target_domain="memory",
            field_path="memory_count",
            operator="gte",
            expected_value=1,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="PolicyMemoryRecord must be persisted upon closed-loop completion",
        ),
    ],
    expected_terminal_state=ExpectedTerminalState(
        execution_status="EXECUTION_COMPLETED",
        outcome_status="PAYMENT_SUCCESS",
        is_terminal=True,
        learning_eligible=True,
    ),
    tags=["smoke", "closed_loop", "happy_path"],
    seed=42,
)

# 2. SMOKE_PAYMENT_FAILURE
SCENARIO_SMOKE_PAYMENT_FAILURE = BenchmarkScenario(
    scenario_id="SMOKE_PAYMENT_FAILURE",
    description="Payment failure recovery path: Execution completed, checkout payment fails, 0 reward recorded, learning eligible in denominator.",
    category=ScenarioCategory.OUTCOME,
    merchant_id="merch_bench_smoke",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with 15.6 inch laptop compartment",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_smoke_merchant(),
        products=_create_smoke_products(),
        active_policy_id="cand_smoke_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    payment_status_override="failed",
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="fail_exp_outcome_status",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="outcome",
            field_path="outcome_status",
            operator="eq",
            expected_value="PAYMENT_FAILED",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Outcome status must be PAYMENT_FAILED",
        ),
        BenchmarkExpectation(
            expectation_id="fail_exp_is_terminal",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="outcome",
            field_path="is_terminal",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Payment failure is terminal",
        ),
        BenchmarkExpectation(
            expectation_id="fail_exp_learning_eligible",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="outcome",
            field_path="learning_eligible",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
            description="Failed payments are learning eligible for non-purchase feedback",
        ),
        BenchmarkExpectation(
            expectation_id="fail_exp_reward_zero",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="eq",
            expected_value=0,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Payment failure gross contribution reward must be 0 paise",
        ),
    ],
    expected_terminal_state=ExpectedTerminalState(
        outcome_status="PAYMENT_FAILED",
        is_terminal=True,
        learning_eligible=True,
        reward_contribution_paise=0,
    ),
    tags=["smoke", "outcome", "payment_failure"],
    seed=42,
)

# 3. SMOKE_NO_OFFER
SCENARIO_SMOKE_NO_OFFER = BenchmarkScenario(
    scenario_id="SMOKE_NO_OFFER",
    description="No-offer baseline path: Unrealistic budget forces baseline selection; execution boundary is not traversed.",
    category=ScenarioCategory.SAFETY,
    merchant_id="merch_bench_smoke",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 50 rupees with laptop sleeve",  # Unrealistically low budget
    ),
    initial_state=InitialStateSpec(
        merchant=_create_smoke_merchant(),
        products=_create_smoke_products(),
        active_policy_id="cand_smoke_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=False,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="no_offer_exp_strategy",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="decision",
            field_path="selected_strategy",
            operator="eq",
            expected_value="NO_OFFER",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="System must select NO_OFFER strategy when budget cannot be satisfied safely",
        ),
        BenchmarkExpectation(
            expectation_id="no_offer_exp_no_execution_id",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="boundary",
            field_path="execution_id",
            operator="is_none",
            expected_value=None,
            failure_class=FailureClass.SAFETY_FAILURE,
            description="NO_OFFER decision must not create boundary execution record",
        ),
        BenchmarkExpectation(
            expectation_id="no_offer_exp_no_order",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="boundary",
            field_path="order_id",
            operator="is_none",
            expected_value=None,
            failure_class=FailureClass.SAFETY_FAILURE,
            description="NO_OFFER decision must not create an Order in Phase 5",
        ),
    ],
    expected_terminal_state=ExpectedTerminalState(
        selected_strategy="NO_OFFER",
    ),
    tags=["smoke", "baseline", "no_offer"],
    seed=42,
)

# 4. SMOKE_REPLAY_IDEMPOTENCY
SCENARIO_SMOKE_REPLAY_IDEMPOTENCY = BenchmarkScenario(
    scenario_id="SMOKE_REPLAY_IDEMPOTENCY",
    description="Replay idempotency: Duplicate execution request replays prior authorization without duplicate order or duplicate memory write.",
    category=ScenarioCategory.RESILIENCE,
    merchant_id="merch_bench_smoke",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with 15.6 inch laptop compartment",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_smoke_merchant(),
        products=_create_smoke_products(),
        active_policy_id="cand_smoke_base",
    ),
    input_overrides={
        "test_replay_execution": True,
        "execution_idempotency_key": "idem_bench_smoke_rep_01",
        "test_replay_outcome": True,
        "outcome_idempotency_key": "idem_bench_smoke_out_01",
    },
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="replay_exp_dup_exec",
            expectation_type=ExpectationType.CONSERVATION,
            target_domain="boundary",
            field_path="is_duplicate_execution",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Replayed boundary execution must detect duplicate idempotency key",
        ),
        BenchmarkExpectation(
            expectation_id="replay_exp_dup_outcome",
            expectation_type=ExpectationType.CONSERVATION,
            target_domain="outcome",
            field_path="is_duplicate_outcome",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Replayed outcome feedback must return cached record with is_duplicate=True",
        ),
    ],
    expected_terminal_state=ExpectedTerminalState(
        execution_status="EXECUTION_COMPLETED",
        outcome_status="PAYMENT_SUCCESS",
    ),
    tags=["smoke", "idempotency", "replay"],
    seed=42,
)


def _init_smoke_registry():
    """Register all initial smoke scenarios into BenchmarkRegistry."""
    BenchmarkRegistry.register(SCENARIO_SMOKE_HAPPY_PATH)
    BenchmarkRegistry.register(SCENARIO_SMOKE_PAYMENT_FAILURE)
    BenchmarkRegistry.register(SCENARIO_SMOKE_NO_OFFER)
    BenchmarkRegistry.register(SCENARIO_SMOKE_REPLAY_IDEMPOTENCY)


_init_smoke_registry()
