"""Governance & Security Benchmark Scenarios for Phase 11.5.

Contracts:
- benchmark-scenario/v1
Categories: LIFECYCLE, SECURITY, CONCURRENCY, AUTHORIZATION, RECOVERY

Defines 3 canonical closed-loop adversarial benchmark scenarios:
1. SCENARIO_GOV_CONCURRENT_LIFECYCLE_CONFLICT (Mismatched predecessor rejected with conflict semantics)
2. SCENARIO_SEC_TENANT_AUTHORIZATION_ATTACK (Cross-tenant decision execution blocked by boundary)
3. SCENARIO_REC_FAILURE_RETRY_RECOVERY (Full-system recovery with monotonic terminal state & zero duplicate effects)
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


def _create_gov_merchant(
    merchant_id: str = "merch_gov_adv",
    name: str = "Governance Security Merchant",
    min_margin: float = 15.0,
    max_discount: float = 25.0,
    objective: str = "BALANCE_REVENUE_AND_MARGIN",
) -> InitialMerchantSpec:
    return InitialMerchantSpec(
        merchant_id=merchant_id,
        name=name,
        currency="INR",
        status="ACTIVE",
        business_objective=objective,
        minimum_margin_percent=min_margin,
        maximum_discount_percent=max_discount,
        target_aov_paise=500000,
    )


def _create_gov_products(merchant_id: str = "merch_gov_adv") -> List[InitialProductSpec]:
    return [
        InitialProductSpec(
            product_id=f"prod_gov_{merchant_id}_01",
            name="Security Guard Pack 40L",
            sku=f"SKU-GOV-{merchant_id[:4].upper()}-01",
            category="travel_backpack",
            price_paise=450000,
            cost_paise=225000,  # 50% margin
            inventory_quantity=20,
            attributes={"laptop_size": 15.6, "water_resistant": True},
            is_active=True,
        ),
        InitialProductSpec(
            product_id=f"prod_gov_{merchant_id}_02",
            name="Encrypted Commuter Sling 15L",
            sku=f"SKU-GOV-{merchant_id[:4].upper()}-02",
            category="travel_backpack",
            price_paise=300000,
            cost_paise=150000,  # 50% margin
            inventory_quantity=20,
            attributes={"laptop_size": 13.3, "water_resistant": True},
            is_active=True,
        ),
    ]


# ==============================================================================
# 1. SCENARIO 1: CONCURRENT LIFECYCLE CONFLICT (Area C & Area B)
# ==============================================================================
SCENARIO_GOV_CONCURRENT_LIFECYCLE_CONFLICT = BenchmarkScenario(
    scenario_id="GOV_CONCURRENT_LIFECYCLE_CONFLICT",
    description="Conflicting lifecycle mutation with mismatched expected predecessor is rejected with conflict semantics and leaves active policy intact.",
    category=ScenarioCategory.CONCURRENCY,
    merchant_id="merch_gov_concurrency",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with laptop protection",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_gov_merchant(merchant_id="merch_gov_concurrency", name="Lifecycle Concurrency Merchant"),
        products=_create_gov_products(merchant_id="merch_gov_concurrency"),
        active_policy_id="cand_gov_stable_base",
    ),
    execution_mode=BenchmarkExecutionMode.DECISION_ONLY,
    input_overrides={
        "attempt_lifecycle_promotion": True,
        "promotion_target_policy_id": "cand_gov_stale_target",
        "expected_previous_policy_id": "cand_wrong_predecessor_id",
    },
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="gov_conflict_status_conflict",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="lifecycle",
            field_path="promotion_status",
            operator="eq",
            expected_value="CONFLICT",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Promotion with mismatched expected predecessor must fail with CONFLICT status",
        ),
        BenchmarkExpectation(
            expectation_id="gov_conflict_failure_code_predecessor_mismatch",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="lifecycle",
            field_path="promotion_failure_code",
            operator="eq",
            expected_value="PREDECESSOR_MISMATCH",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Failure code must explicitly be PREDECESSOR_MISMATCH",
        ),
        BenchmarkExpectation(
            expectation_id="gov_conflict_active_policy_unchanged",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="active_policy",
            field_path="active_policy_id",
            operator="eq",
            expected_value="cand_gov_stable_base",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Active policy pointer must remain unchanged on conflicting mutation",
        ),
    ],
)


# ==============================================================================
# 2. SCENARIO 2: TENANT AUTHORIZATION ATTACK (Area D)
# ==============================================================================
SCENARIO_SEC_TENANT_AUTHORIZATION_ATTACK = BenchmarkScenario(
    scenario_id="SEC_TENANT_AUTHORIZATION_ATTACK",
    description="Attacker merchant attempts to execute victim merchant's decision; backend boundary rejects with DecisionTenantViolationError, 0 orders, 0 payments.",
    category=ScenarioCategory.AUTHORIZATION,
    merchant_id="merch_sec_victim",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_gov_merchant(merchant_id="merch_sec_victim", name="Victim Tenant Merchant"),
        products=_create_gov_products(merchant_id="merch_sec_victim"),
        active_policy_id="cand_sec_victim_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    input_overrides={
        "test_cross_tenant_attack": True,
        "attacker_merchant_id": "merch_sec_attacker",
    },
    simulate_payment=True,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="sec_cross_tenant_rejected_true",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="security",
            field_path="cross_tenant_rejected",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.TENANT_ISOLATION_FAILURE,
            description="Cross-tenant execution attempt must be strictly rejected at authoritative boundary",
        ),
        BenchmarkExpectation(
            expectation_id="sec_victim_execution_completed",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="boundary",
            field_path="boundary_status",
            operator="eq",
            expected_value="EXECUTION_COMPLETED",
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Victim's authorized execution proceeds cleanly without cross-talk",
        ),
        BenchmarkExpectation(
            expectation_id="sec_victim_active_policy_preserved",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="active_policy",
            field_path="active_policy_id",
            operator="eq",
            expected_value="cand_sec_victim_base",
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Victim merchant's active policy must not be altered by cross-tenant attack",
        ),
    ],
)


# ==============================================================================
# 3. SCENARIO 3: FULL-SYSTEM FAILURE RECOVERY (Area G)
# ==============================================================================
SCENARIO_REC_FAILURE_RETRY_RECOVERY = BenchmarkScenario(
    scenario_id="REC_FAILURE_RETRY_RECOVERY",
    description="Full closed-loop recovery with retry idempotency, achieving monotonic terminal state and exactly one effective learning update.",
    category=ScenarioCategory.RECOVERY,
    merchant_id="merch_rec_recovery",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_gov_merchant(merchant_id="merch_rec_recovery", name="Recovery System Merchant"),
        products=_create_gov_products(merchant_id="merch_rec_recovery"),
        active_policy_id="cand_rec_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    input_overrides={
        "test_replay_execution": True,
        "execution_idempotency_key": "idem_rec_exec_001",
        "outcome_idempotency_key": "idem_rec_out_001",
    },
    simulate_payment=True,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="rec_terminal_state_monotonic",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="outcome",
            field_path="is_terminal",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Outcome state after recovery must be terminal",
        ),
        BenchmarkExpectation(
            expectation_id="rec_outcome_status_payment_success",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="outcome",
            field_path="outcome_status",
            operator="eq",
            expected_value="PAYMENT_SUCCESS",
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Terminal outcome status must be PAYMENT_SUCCESS",
        ),
        BenchmarkExpectation(
            expectation_id="rec_duplicate_execution_flag_true",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="boundary",
            field_path="is_duplicate_execution",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Replayed retry execution must be recognized as duplicate with zero state drift",
        ),
        BenchmarkExpectation(
            expectation_id="rec_single_model_observation",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="learning",
            field_path="model_observation_count",
            operator="eq",
            expected_value=1,
            failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
            description="Exactly one effective model observation must be recorded despite retry",
        ),
    ],
)


GOVERNANCE_SECURITY_SCENARIOS = [
    SCENARIO_GOV_CONCURRENT_LIFECYCLE_CONFLICT,
    SCENARIO_SEC_TENANT_AUTHORIZATION_ATTACK,
    SCENARIO_REC_FAILURE_RETRY_RECOVERY,
]
