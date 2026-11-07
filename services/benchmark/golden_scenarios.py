"""Golden End-to-End Adversarial Validation Suite for Phase 11.2.

Contract: benchmark-scenario/v1
Tag: GOLDEN_E2E_ADVERSARIAL

Defines 10 cross-layer golden scenarios attacking the complete closed loop:
1. GOLDEN_PAYMENT_FAILURE_TRUTH (Outcome / Learning)
2. GOLDEN_NO_OFFER_SHORT_CIRCUIT (Selection / Execution)
3. GOLDEN_SAFETY_REJECTION_BLOCK (Safety / Boundary)
4. GOLDEN_STALE_STATE_REJECTION (Boundary / Race Condition)
5. GOLDEN_DUPLICATE_OUTCOME_ONCE (Replay / Idempotency)
6. GOLDEN_LUCKY_PURCHASE_GATE (Lifecycle / Evidence Firewall)
7. GOLDEN_LEARNING_NO_PROMOTION (Learning vs Active Policy)
8. GOLDEN_MERCHANT_BOUNDARY_ATTACK (Multi-Tenant Security)
9. GOLDEN_NEGATIVE_CONTRIBUTION (Economics / Signed Contribution)
10. GOLDEN_EXECUTION_FAILURE_SHIELD (Execution / Payment Shield)
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
    ExpectedTerminalState,
    BenchmarkExpectation,
    ExpectationType,
    FailureClass,
)
from services.benchmark.registry import BenchmarkRegistry


def _create_golden_merchant(merchant_id: str = "merch_golden_adv") -> InitialMerchantSpec:
    return InitialMerchantSpec(
        merchant_id=merchant_id,
        name="Golden Adversarial Merchant",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=15.0,
        maximum_discount_percent=25.0,
        target_aov_paise=500000,
    )


def _create_golden_products(merchant_id: str = "merch_golden_adv") -> List[InitialProductSpec]:
    return [
        InitialProductSpec(
            product_id=f"prod_gold_{merchant_id}_01",
            name="Expedition Pack 40L",
            sku="SKU-GLD-01",
            category="travel_backpack",
            price_paise=450000,
            cost_paise=250000,  # 44% margin
            inventory_quantity=20,
            attributes={"laptop_size": 16.0, "water_resistant": True},
            is_active=True,
        ),
        InitialProductSpec(
            product_id=f"prod_gold_{merchant_id}_02",
            name="Daily Commuter 20L",
            sku="SKU-GLD-02",
            category="travel_backpack",
            price_paise=300000,
            cost_paise=150000,  # 50% margin
            inventory_quantity=20,
            attributes={"laptop_size": 14.0, "water_resistant": False},
            is_active=True,
        ),
    ]


# ==============================================================================
# 1. SCENARIO 1: PAYMENT FAILURE MUST NOT BECOME POSITIVE LEARNING
# ==============================================================================
SCENARIO_1_PAYMENT_FAILURE_TRUTH = BenchmarkScenario(
    scenario_id="GOLDEN_PAYMENT_FAILURE_TRUTH",
    description="Payment failure must not manufacture positive contribution or reward inflation; recorded as zero-reward non-purchase.",
    category=ScenarioCategory.OUTCOME,
    merchant_id="merch_golden_adv",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with 16 inch laptop compartment",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_golden_merchant(),
        products=_create_golden_products(),
        active_policy_id="cand_golden_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    payment_status_override="failed",
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="scen1_boundary_completed",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="boundary",
            field_path="boundary_status",
            operator="eq",
            expected_value="EXECUTION_COMPLETED",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Phase 9.2 boundary authorization must complete normally before checkout",
        ),
        BenchmarkExpectation(
            expectation_id="scen1_payment_status_failed",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="outcome",
            field_path="outcome_status",
            operator="eq",
            expected_value="PAYMENT_FAILED",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Terminal payment state must be PAYMENT_FAILED",
        ),
        BenchmarkExpectation(
            expectation_id="scen1_reward_zero",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="eq",
            expected_value=0,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Failed checkout reward contribution must be strictly 0 paise",
        ),
        BenchmarkExpectation(
            expectation_id="scen1_learning_eligible_denominator",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="outcome",
            field_path="learning_eligible",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
            description="Failed payment remains learning-eligible for non-purchase feedback",
        ),
        BenchmarkExpectation(
            expectation_id="scen1_active_policy_unchanged",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="active_policy",
            field_path="active_policy_id",
            operator="eq",
            expected_value="cand_golden_base",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Active policy pointer must remain unchanged",
        ),
    ],
    expected_terminal_state=ExpectedTerminalState(
        outcome_status="PAYMENT_FAILED",
        is_terminal=True,
        learning_eligible=True,
        reward_contribution_paise=0,
    ),
    tags=["golden", "GOLDEN_E2E_ADVERSARIAL", "outcome", "learning"],
    seed=101,
)

# ==============================================================================
# 2. SCENARIO 2: NO_OFFER MUST SHORT-CIRCUIT COMMERCIAL EXECUTION
# ==============================================================================
SCENARIO_2_NO_OFFER_SHORT_CIRCUIT = BenchmarkScenario(
    scenario_id="GOLDEN_NO_OFFER_SHORT_CIRCUIT",
    description="Baseline NO_OFFER selection must short-circuit commercial execution; zero orders, zero payments, zero memory writes.",
    category=ScenarioCategory.DECISION,
    merchant_id="merch_golden_no_offer",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5 rupees",  # Unfeasible budget
    ),
    initial_state=InitialStateSpec(
        merchant=_create_golden_merchant("merch_golden_no_offer"),
        products=_create_golden_products("merch_golden_no_offer"),
        active_policy_id="cand_golden_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=False,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="scen2_selected_strategy_no_offer",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="decision",
            field_path="selected_strategy",
            operator="eq",
            expected_value="NO_OFFER",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="System must select canonical baseline NO_OFFER",
        ),
        BenchmarkExpectation(
            expectation_id="scen2_no_execution_record",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="boundary",
            field_path="execution_id",
            operator="is_none",
            expected_value=None,
            failure_class=FailureClass.SAFETY_FAILURE,
            description="NO_OFFER must not create DecisionExecutionRecord",
        ),
        BenchmarkExpectation(
            expectation_id="scen2_no_order_created",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="boundary",
            field_path="order_id",
            operator="is_none",
            expected_value=None,
            failure_class=FailureClass.SAFETY_FAILURE,
            description="NO_OFFER must not create Order in Phase 5",
        ),
        BenchmarkExpectation(
            expectation_id="scen2_zero_memories_written",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="memory",
            field_path="memory_count",
            operator="eq",
            expected_value=0,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Short-circuited NO_OFFER must write zero purchase memories",
        ),
    ],
    expected_terminal_state=ExpectedTerminalState(
        selected_strategy="NO_OFFER",
    ),
    tags=["golden", "GOLDEN_E2E_ADVERSARIAL", "selection", "execution"],
    seed=102,
)

# ==============================================================================
# 3. SCENARIO 3: FAILED SAFETY MUST BLOCK EXECUTION
# ==============================================================================
SCENARIO_3_SAFETY_REJECTION_BLOCK = BenchmarkScenario(
    scenario_id="GOLDEN_SAFETY_REJECTION_BLOCK",
    description="Inadmissible candidate (e.g. stockout) must be blocked by Phase 8.6 safety gate; boundary rejects with SAFETY_REJECTED.",
    category=ScenarioCategory.SAFETY,
    merchant_id="merch_golden_adv_stockout",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with 16 inch laptop compartment",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_golden_merchant("merch_golden_adv_stockout"),
        products=[
            InitialProductSpec(
                product_id="prod_gold_stockout_01",
                name="Depleted Stock Pack",
                sku="SKU-DEP-01",
                category="travel_backpack",
                price_paise=450000,
                cost_paise=250000,
                inventory_quantity=0,  # 0 Inventory!
                attributes={"laptop_size": 16.0},
                is_active=True,
            )
        ],
        active_policy_id="cand_golden_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=False,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="scen3_no_order_created",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="boundary",
            field_path="order_id",
            operator="is_none",
            expected_value=None,
            failure_class=FailureClass.SAFETY_FAILURE,
            description="Failed safety check must prevent order creation",
        ),
        BenchmarkExpectation(
            expectation_id="scen3_no_payment_attempted",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="outcome",
            field_path="outcome_id",
            operator="is_none",
            expected_value=None,
            failure_class=FailureClass.SAFETY_FAILURE,
            description="Failed safety check must prevent outcome processing",
        ),
        BenchmarkExpectation(
            expectation_id="scen3_active_policy_unchanged",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="active_policy",
            field_path="active_policy_id",
            operator="eq",
            expected_value="cand_golden_base",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Active policy pointer must remain unchanged",
        ),
    ],
    tags=["golden", "GOLDEN_E2E_ADVERSARIAL", "safety", "boundary"],
    seed=103,
)

# ==============================================================================
# 4. SCENARIO 4: STALE STATE MUST BE REJECTED AT THE FINAL BOUNDARY
# ==============================================================================
SCENARIO_4_STALE_STATE_REJECTION = BenchmarkScenario(
    scenario_id="GOLDEN_STALE_STATE_REJECTION",
    description="State changes between decision and boundary execution (inventory depleted to 0); boundary fails closed with SAFETY_REJECTED.",
    category=ScenarioCategory.RESILIENCE,
    merchant_id="merch_golden_stale",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with 16 inch laptop compartment",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_golden_merchant("merch_golden_stale"),
        products=_create_golden_products("merch_golden_stale"),
        active_policy_id="cand_golden_base",
    ),
    input_overrides={
        "mutate_inventory_before_execution": 0,  # Deplete inventory between decision and execution!
    },
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=False,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="scen4_boundary_rejected",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="boundary",
            field_path="boundary_status",
            operator="eq",
            expected_value="SAFETY_REJECTED",
            failure_class=FailureClass.SAFETY_FAILURE,
            description="Boundary execution must reject decision due to fresh state mismatch",
        ),
        BenchmarkExpectation(
            expectation_id="scen4_stale_flag_set",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="boundary",
            field_path="stale_state_rejected",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.SAFETY_FAILURE,
            description="Stale state rejection must be recorded in observation snapshot",
        ),
        BenchmarkExpectation(
            expectation_id="scen4_no_order",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="boundary",
            field_path="order_id",
            operator="is_none",
            expected_value=None,
            failure_class=FailureClass.SAFETY_FAILURE,
            description="Stale boundary traversal must not create order",
        ),
    ],
    tags=["golden", "GOLDEN_E2E_ADVERSARIAL", "race_condition", "boundary"],
    seed=104,
)

# ==============================================================================
# 5. SCENARIO 5: DUPLICATE OUTCOME MUST NOT CREATE DUPLICATE LEARNING EFFECT
# ==============================================================================
SCENARIO_5_DUPLICATE_OUTCOME_ONCE = BenchmarkScenario(
    scenario_id="GOLDEN_DUPLICATE_OUTCOME_ONCE",
    description="At-least-once outcome delivery replays cached outcome; produces exactly-once effective memory and model update.",
    category=ScenarioCategory.RESILIENCE,
    merchant_id="merch_golden_duplicate",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with 16 inch laptop compartment",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_golden_merchant("merch_golden_duplicate"),
        products=_create_golden_products("merch_golden_duplicate"),
        active_policy_id="cand_golden_base",
    ),
    input_overrides={
        "test_replay_outcome": True,
        "outcome_idempotency_key": "idem_golden_dup_out_01",
    },
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="scen5_is_duplicate_outcome",
            expectation_type=ExpectationType.CONSERVATION,
            target_domain="outcome",
            field_path="is_duplicate_outcome",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Duplicate outcome feedback call must return is_duplicate=True",
        ),
        BenchmarkExpectation(
            expectation_id="scen5_outcome_status_success",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="outcome",
            field_path="outcome_status",
            operator="eq",
            expected_value="PAYMENT_SUCCESS",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Terminal status remains PAYMENT_SUCCESS",
        ),
        BenchmarkExpectation(
            expectation_id="scen5_monotonic_terminal",
            expectation_type=ExpectationType.MONOTONICITY,
            target_domain="outcome",
            field_path="is_terminal",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Terminal state remains monotonic under duplicate delivery",
        ),
    ],
    tags=["golden", "GOLDEN_E2E_ADVERSARIAL", "replay", "idempotency"],
    seed=105,
)

# ==============================================================================
# 6. SCENARIO 6: SINGLE LUCKY PURCHASE MUST NOT PROMOTE A POLICY
# ==============================================================================
SCENARIO_6_LUCKY_PURCHASE_GATE = BenchmarkScenario(
    scenario_id="GOLDEN_LUCKY_PURCHASE_GATE",
    description="A candidate policy with only 1 observation attempts promotion; rejected with INSUFFICIENT_EVIDENCE.",
    category=ScenarioCategory.LIFECYCLE,
    merchant_id="merch_golden_lifecycle",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with 16 inch laptop compartment",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_golden_merchant("merch_golden_lifecycle"),
        products=_create_golden_products("merch_golden_lifecycle"),
        active_policy_id="cand_golden_base",
    ),
    input_overrides={
        "attempt_lifecycle_promotion": True,
        "promotion_target_policy_id": "cand_single_lucky_purchase",
    },
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="scen6_promotion_status_insufficient",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="lifecycle",
            field_path="promotion_status",
            operator="eq",
            expected_value="INSUFFICIENT_EVIDENCE",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Promotion evaluator must reject candidate with INSUFFICIENT_EVIDENCE",
        ),
        BenchmarkExpectation(
            expectation_id="scen6_failure_code_sample_size",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="lifecycle",
            field_path="promotion_failure_code",
            operator="eq",
            expected_value="INSUFFICIENT_SAMPLE_SIZE",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Failure code must be INSUFFICIENT_SAMPLE_SIZE",
        ),
        BenchmarkExpectation(
            expectation_id="scen6_active_policy_untouched",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="active_policy",
            field_path="active_policy_id",
            operator="eq",
            expected_value="cand_golden_base",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Active policy pointer must remain cand_golden_base",
        ),
    ],
    tags=["golden", "GOLDEN_E2E_ADVERSARIAL", "lifecycle", "promotion"],
    seed=106,
)

# ==============================================================================
# 7. SCENARIO 7: LEARNING MUST NOT MUTATE ACTIVE POLICY
# ==============================================================================
SCENARIO_7_LEARNING_NO_PROMOTION = BenchmarkScenario(
    scenario_id="GOLDEN_LEARNING_NO_PROMOTION",
    description="Online model parameter updates occur upon payment capture; production active policy pointer remains untouched.",
    category=ScenarioCategory.LEARNING,
    merchant_id="merch_golden_learning",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with 16 inch laptop compartment",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_golden_merchant("merch_golden_learning"),
        products=_create_golden_products("merch_golden_learning"),
        active_policy_id="cand_golden_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="scen7_memory_persisted",
            expectation_type=ExpectationType.RELATIONAL,
            target_domain="memory",
            field_path="memory_count",
            operator="gte",
            expected_value=1,
            failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
            description="Learning memory record must be persisted",
        ),
        BenchmarkExpectation(
            expectation_id="scen7_model_observation_updated",
            expectation_type=ExpectationType.RELATIONAL,
            target_domain="model",
            field_path="model_observation_count",
            operator="gte",
            expected_value=1,
            failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
            description="Bandit model observation count must be updated",
        ),
        BenchmarkExpectation(
            expectation_id="scen7_active_policy_immutable",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="active_policy",
            field_path="active_policy_id",
            operator="eq",
            expected_value="cand_golden_base",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Active policy pointer must NOT mutate solely because model learning occurred",
        ),
    ],
    tags=["golden", "GOLDEN_E2E_ADVERSARIAL", "learning", "lifecycle"],
    seed=107,
)

# ==============================================================================
# 8. SCENARIO 8: MERCHANT BOUNDARY ATTACK
# ==============================================================================
SCENARIO_8_MERCHANT_BOUNDARY_ATTACK = BenchmarkScenario(
    scenario_id="GOLDEN_MERCHANT_BOUNDARY_ATTACK",
    description="Cross-tenant boundary attack: Merchant A attempts to execute Decision belonging to Merchant B; rejected with DecisionTenantViolationError.",
    category=ScenarioCategory.TENANT,
    merchant_id="merch_golden_victim",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with 16 inch laptop compartment",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_golden_merchant("merch_golden_victim"),
        products=_create_golden_products("merch_golden_victim"),
        active_policy_id="cand_golden_base",
    ),
    input_overrides={
        "test_cross_tenant_attack": True,
        "attacker_merchant_id": "merch_golden_attacker",
    },
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=False,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="scen8_cross_tenant_rejected",
            expectation_type=ExpectationType.ISOLATION,
            target_domain="tenant",
            field_path="cross_tenant_rejected",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.TENANT_ISOLATION_FAILURE,
            description="Cross-tenant execution request must be rejected with TenantViolationError",
        ),
        BenchmarkExpectation(
            expectation_id="scen8_victim_merchant_preserved",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="tenant",
            field_path="merchant_id",
            operator="eq",
            expected_value="merch_golden_victim",
            failure_class=FailureClass.TENANT_ISOLATION_FAILURE,
            description="Merchant scope must remain strictly bound to victim",
        ),
    ],
    tags=["golden", "GOLDEN_E2E_ADVERSARIAL", "tenant", "security"],
    seed=108,
)

# ==============================================================================
# 9. SCENARIO 9: NEGATIVE CONTRIBUTION MUST REMAIN NEGATIVE
# ==============================================================================
SCENARIO_9_NEGATIVE_CONTRIBUTION = BenchmarkScenario(
    scenario_id="GOLDEN_NEGATIVE_CONTRIBUTION",
    description="Unprofitable sale (Cost > Price) produces signed negative contribution; formula preserves signed value without clipping to zero.",
    category=ScenarioCategory.ECONOMICS,
    merchant_id="merch_golden_loss_leader",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with 16 inch laptop compartment",
    ),
    initial_state=InitialStateSpec(
        merchant=InitialMerchantSpec(
            merchant_id="merch_golden_loss_leader",
            name="Loss Leader Merchant",
            minimum_margin_percent=-100.0,  # Explicitly allow loss-leader negative margins
            maximum_discount_percent=50.0,
        ),
        products=[
            InitialProductSpec(
                product_id="prod_gold_loss_01",
                name="Loss Leader Pack 30L",
                sku="SKU-LOSS-01",
                category="travel_backpack",
                price_paise=300000,  # Price: 300,000 paise (₹3,000)
                cost_paise=450000,   # Cost: 450,000 paise (₹4,500) -> Negative contribution!
                inventory_quantity=20,
                attributes={"laptop_size": 16.0},
                is_active=True,
            )
        ],
        active_policy_id="cand_golden_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="scen9_contribution_negative",
            expectation_type=ExpectationType.RELATIONAL,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="lt",
            expected_value=0,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Reward contribution must be strictly negative (not clipped to 0)",
        ),
        BenchmarkExpectation(
            expectation_id="scen9_exact_negative_amount",
            expectation_type=ExpectationType.RELATIONAL,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="lte",
            expected_value=-150000,  # Negative contribution at least -150,000 paise (-₹1,500)
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Contribution must be negative, at least -150,000 paise",
        ),
    ],
    tags=["golden", "GOLDEN_E2E_ADVERSARIAL", "economics", "reward"],
    seed=109,
)

# ==============================================================================
# 10. SCENARIO 10: FAILED EXECUTION MUST NOT BECOME SUCCESSFUL PAYMENT
# ==============================================================================
SCENARIO_10_EXECUTION_FAILURE_SHIELD = BenchmarkScenario(
    scenario_id="GOLDEN_EXECUTION_FAILURE_SHIELD",
    description="Upstream boundary execution rejection cannot be bypassed or upgraded to a successful payment.",
    category=ScenarioCategory.EXECUTION,
    merchant_id="merch_golden_retire",
    buyer_context=BuyerContextInput(
        raw_prompt="travel backpack under 5000 with 16 inch laptop compartment",
    ),
    initial_state=InitialStateSpec(
        merchant=InitialMerchantSpec(
            merchant_id="merch_golden_retire",
            name="Retire Policy Merchant",
            status="ACTIVE",
        ),
        products=_create_golden_products("merch_golden_retire"),
        active_policy_id="cand_golden_base",
    ),
    input_overrides={
        "retire_policy_before_execution": True,  # Policy retired right before boundary execution!
    },
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=False,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="scen10_boundary_retired",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="boundary",
            field_path="boundary_status",
            operator="eq",
            expected_value="POLICY_RETIRED",
            failure_class=FailureClass.SAFETY_FAILURE,
            description="Boundary execution must reject retired policy",
        ),
        BenchmarkExpectation(
            expectation_id="scen10_no_order_id",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="boundary",
            field_path="order_id",
            operator="is_none",
            expected_value=None,
            failure_class=FailureClass.SAFETY_FAILURE,
            description="Rejected execution must never produce order_id",
        ),
        BenchmarkExpectation(
            expectation_id="scen10_no_payment_success",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="outcome",
            field_path="outcome_status",
            operator="ne",
            expected_value="PAYMENT_SUCCESS",
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Outcome status must NEVER be PAYMENT_SUCCESS for failed execution",
        ),
    ],
    tags=["golden", "GOLDEN_E2E_ADVERSARIAL", "execution", "boundary"],
    seed=110,
)


# List of all 10 golden scenarios
GOLDEN_SCENARIO_SUITE: List[BenchmarkScenario] = [
    SCENARIO_1_PAYMENT_FAILURE_TRUTH,
    SCENARIO_2_NO_OFFER_SHORT_CIRCUIT,
    SCENARIO_3_SAFETY_REJECTION_BLOCK,
    SCENARIO_4_STALE_STATE_REJECTION,
    SCENARIO_5_DUPLICATE_OUTCOME_ONCE,
    SCENARIO_6_LUCKY_PURCHASE_GATE,
    SCENARIO_7_LEARNING_NO_PROMOTION,
    SCENARIO_8_MERCHANT_BOUNDARY_ATTACK,
    SCENARIO_9_NEGATIVE_CONTRIBUTION,
    SCENARIO_10_EXECUTION_FAILURE_SHIELD,
]


def register_golden_scenarios():
    """Register all 10 golden scenarios into BenchmarkRegistry."""
    for scen in GOLDEN_SCENARIO_SUITE:
        BenchmarkRegistry.register(scen)


register_golden_scenarios()
