"""Adaptive Integrity Benchmark Scenarios for Phase 11.4.

Contract: benchmark-scenario/v1
Categories: EXPLORATION, LEARNING, TEMPORAL

Defines 3 canonical closed-loop adaptive benchmark scenarios:
1. ADAPTIVE_EXPLORATION_BUDGET_EXHAUSTED (Exploration budget/exposure exhaustion)
2. ADAPTIVE_DUPLICATE_LEARNING_REPLAY (At-least-once delivery with single effective model update)
3. ADAPTIVE_FUTURE_EVIDENCE_REJECTED (Point-in-time temporal leakage prevention)
"""

from typing import List
from services.benchmark.schemas import (
    BenchmarkScenario,
    ScenarioCategory,
    BenchmarkExecutionMode,
    BuyerContextInput,
    InitialStateSpec,
    InitialMerchantSpec,
    InitialProductSpec,
    BenchmarkExpectation,
    ExpectationType,
    FailureClass,
)


def _create_adaptive_merchant(
    merchant_id: str = "merch_adapt_adv",
    min_margin: float = 15.0,
    max_discount: float = 25.0,
    objective: str = "BALANCE_REVENUE_AND_MARGIN",
) -> InitialMerchantSpec:
    return InitialMerchantSpec(
        merchant_id=merchant_id,
        name="Adaptive Integrity Merchant",
        currency="INR",
        status="ACTIVE",
        business_objective=objective,
        minimum_margin_percent=min_margin,
        maximum_discount_percent=max_discount,
        target_aov_paise=500000,
    )


def _create_adaptive_products(merchant_id: str = "merch_adapt_adv") -> List[InitialProductSpec]:
    return [
        InitialProductSpec(
            product_id=f"prod_adapt_{merchant_id}_01",
            name="Tactical Expedition Pack 35L",
            sku="SKU-ADP-01",
            category="travel_backpack",
            price_paise=400000,
            cost_paise=200000,  # 50% margin
            inventory_quantity=20,
            attributes={"laptop_size": 15.6, "water_resistant": True},
            is_active=True,
        ),
        InitialProductSpec(
            product_id=f"prod_adapt_{merchant_id}_02",
            name="Compact Daily Sling 10L",
            sku="SKU-ADP-02",
            category="travel_backpack",
            price_paise=250000,
            cost_paise=125000,  # 50% margin
            inventory_quantity=20,
            attributes={"laptop_size": 13.0, "water_resistant": False},
            is_active=True,
        ),
    ]


# ==============================================================================
# 1. SCENARIO 1: EXPLORATION BUDGET EXHAUSTION FALLBACK (Area A)
# ==============================================================================
SCENARIO_ADAPT_EXPLORATION_BUDGET_EXHAUSTED = BenchmarkScenario(
    scenario_id="ADAPTIVE_EXPLORATION_BUDGET_EXHAUSTED",
    description="Merchant with exhausted exploration budget deterministically falls back to exploit mode with zero committed exposure.",
    category=ScenarioCategory.EXPLORATION,
    merchant_id="merch_adapt_exp_exh",
    buyer_context=BuyerContextInput(
        raw_prompt="tactical backpack under 5000 with 15 inch laptop sleeve",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_adaptive_merchant(merchant_id="merch_adapt_exp_exh"),
        products=_create_adaptive_products(merchant_id="merch_adapt_exp_exh"),
        active_policy_id="cand_adapt_exp_base",
    ),
    execution_mode=BenchmarkExecutionMode.DECISION_ONLY,
    input_overrides={
        "seed_exhausted_exploration": True,
    },
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="adapt_exp_decision_mode_exploit",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="decision",
            field_path="decision_mode",
            operator="eq",
            expected_value="EXPLOIT",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Decision mode must fall back to EXPLOIT when exploration budget is exhausted",
        ),
        BenchmarkExpectation(
            expectation_id="adapt_exp_active_policy_preserved",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="lifecycle",
            field_path="active_policy_id",
            operator="eq",
            expected_value="cand_adapt_exp_base",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Active policy must remain cand_adapt_exp_base and not be altered by exploration check",
        ),
    ],
    tags=["exploration", "budget", "fallback", "adaptive"],
)


# ==============================================================================
# 2. SCENARIO 2: DUPLICATE LEARNING REPLAY IDEMPOTENCY (Area B)
# ==============================================================================
SCENARIO_ADAPT_DUPLICATE_LEARNING_REPLAY = BenchmarkScenario(
    scenario_id="ADAPTIVE_DUPLICATE_LEARNING_REPLAY",
    description="Outcome feedback delivered twice; at-least-once delivery results in exactly one effective model update and no reward double-counting.",
    category=ScenarioCategory.LEARNING,
    merchant_id="merch_adapt_replay",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_adaptive_merchant(merchant_id="merch_adapt_replay"),
        products=_create_adaptive_products(merchant_id="merch_adapt_replay"),
        active_policy_id="cand_adapt_replay_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    input_overrides={
        "test_replay_outcome": True,
    },
    simulate_payment=True,
    payment_status_override="captured",
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="adapt_rep_outcome_duplicate_flag",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="outcome",
            field_path="is_duplicate_outcome",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
            description="Second outcome processing must return is_duplicate=True from idempotency cache",
        ),
        BenchmarkExpectation(
            expectation_id="adapt_rep_single_model_observation",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="learning",
            field_path="model_observation_count",
            operator="eq",
            expected_value=1,
            failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
            description="LinUCB model observation count must be exactly 1, proving no duplicate update occurred",
        ),
        BenchmarkExpectation(
            expectation_id="adapt_rep_single_memory_record",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="memory",
            field_path="memory_count",
            operator="eq",
            expected_value=1,
            failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
            description="PolicyMemoryRecord count must be exactly 1, proving exactly-once memory effect",
        ),
        BenchmarkExpectation(
            expectation_id="adapt_rep_active_policy_unchanged",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="lifecycle",
            field_path="active_policy_id",
            operator="eq",
            expected_value="cand_adapt_replay_base",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Active policy must remain cand_adapt_replay_base and never be mutated by model learning",
        ),
    ],
    tags=["learning", "replay", "idempotency", "adaptive"],
)


# ==============================================================================
# 3. SCENARIO 3: TEMPORAL CUTOFF LEAKAGE PREVENTION (Area C)
# ==============================================================================
SCENARIO_ADAPT_FUTURE_EVIDENCE_REJECTED = BenchmarkScenario(
    scenario_id="ADAPTIVE_FUTURE_EVIDENCE_REJECTED",
    description="Candidate policy containing future evidence (observed_at > evaluation_time) is strictly rejected from promotion with FUTURE_EVIDENCE_REJECTED.",
    category=ScenarioCategory.TEMPORAL,
    merchant_id="merch_adapt_temporal",
    buyer_context=BuyerContextInput(
        raw_prompt="commuter backpack under 4000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_adaptive_merchant(merchant_id="merch_adapt_temporal"),
        products=_create_adaptive_products(merchant_id="merch_adapt_temporal"),
        active_policy_id="cand_adapt_temp_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    input_overrides={
        "attempt_lifecycle_promotion": True,
        "promotion_target_policy_id": "cand_adapt_future_treatment",
        "seed_future_evidence": True,
    },
    simulate_payment=True,
    payment_status_override="captured",
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="adapt_temp_promo_status_rejected",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="lifecycle",
            field_path="promotion_status",
            operator="in",
            expected_value=["INSUFFICIENT_EVIDENCE", "NOT_ELIGIBLE", "REJECTED"],
            failure_class=FailureClass.TEMPORAL_INTEGRITY_FAILURE,
            description="Promotion must be rejected when candidate contains future evidence",
        ),
        BenchmarkExpectation(
            expectation_id="adapt_temp_failure_code_future",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="lifecycle",
            field_path="promotion_failure_code",
            operator="eq",
            expected_value="FUTURE_EVIDENCE_REJECTED",
            failure_class=FailureClass.TEMPORAL_INTEGRITY_FAILURE,
            description="Promotion failure code must be explicitly FUTURE_EVIDENCE_REJECTED",
        ),
        BenchmarkExpectation(
            expectation_id="adapt_temp_active_policy_immutable",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="lifecycle",
            field_path="active_policy_id",
            operator="eq",
            expected_value="cand_adapt_temp_base",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Active policy must remain cand_adapt_temp_base and not be mutated by rejected promotion",
        ),
    ],
    tags=["temporal", "lifecycle", "leakage", "adaptive"],
)


ADAPTIVE_SCENARIOS: List[BenchmarkScenario] = [
    SCENARIO_ADAPT_EXPLORATION_BUDGET_EXHAUSTED,
    SCENARIO_ADAPT_DUPLICATE_LEARNING_REPLAY,
    SCENARIO_ADAPT_FUTURE_EVIDENCE_REJECTED,
]


def register_adaptive_scenarios():
    """Register all 3 adaptive scenarios into BenchmarkRegistry."""
    from services.benchmark.registry import BenchmarkRegistry
    for scen in ADAPTIVE_SCENARIOS:
        BenchmarkRegistry.register(scen)


register_adaptive_scenarios()

