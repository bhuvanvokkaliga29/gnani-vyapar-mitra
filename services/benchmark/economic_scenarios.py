"""Economic Boundary and Profit-Integrity Benchmark Scenarios for Phase 11.3.

Contract: benchmark-scenario/v1
Category: ECONOMICS

Defines 11 closed-loop economic adversarial scenarios:
1. ECON_ZERO_CONTRIBUTION_PURCHASE (RealizedRevenue == TotalCOGS -> Contrib = 0)
2. ECON_NEGATIVE_CONTRIBUTION_PRESERVED (Signed negative contribution preserved, no clipping)
3. ECON_REVENUE_NOT_EQUAL_CONTRIBUTION (High revenue, low contribution separation)
4. ECON_BUNDLE_MULTI_ITEM_MATH (Multi-item basket economics and COGS summation)
5. ECON_MULTI_UNIT_QUANTITY_SCALING (COGS scales strictly by requested quantity)
6. ECON_INVENTORY_SAFETY_BARRIER (Economic validity != execution authority on stockout)
7. ECON_NO_OFFER_EQUAL_BASELINE (Candidate <= NO_OFFER baseline selects NO_OFFER)
8. ECON_EXPECTED_VS_OBSERVED_DIVERGENCE (Decision prediction != outcome observation)
9. ECON_REJECTION_ZERO_SIDE_EFFECTS (Margin floor rejection creates zero side effects)
10. ECON_PROMOTION_ECONOMIC_GATE (Positive economics alone cannot bypass sample governance)
11. ECON_CROSS_MERCHANT_ECONOMIC_ISOLATION (Multi-tenant economics strictly isolated)
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


def _create_economic_merchant(
    merchant_id: str = "merch_econ_adv",
    min_margin: float = 15.0,
    max_discount: float = 25.0,
    objective: str = "BALANCE_REVENUE_AND_MARGIN",
) -> InitialMerchantSpec:
    return InitialMerchantSpec(
        merchant_id=merchant_id,
        name="Economic Boundary Merchant",
        currency="INR",
        status="ACTIVE",
        business_objective=objective,
        minimum_margin_percent=min_margin,
        maximum_discount_percent=max_discount,
        target_aov_paise=500000,
    )


# ==============================================================================
# 1. SCENARIO 1: ZERO CONTRIBUTION PURCHASE (Revenue == COGS -> Contrib = 0)
# ==============================================================================
SCENARIO_ECON_ZERO_CONTRIBUTION = BenchmarkScenario(
    scenario_id="ECON_ZERO_CONTRIBUTION_PURCHASE",
    description="Valid executed purchase where RealizedRevenue == TotalCOGS; reward is exactly 0 paise, denominator retained.",
    category=ScenarioCategory.ECONOMICS,
    merchant_id="merch_econ_zero",
    buyer_context=BuyerContextInput(
        raw_prompt="minimal travel backpack under 4000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_economic_merchant(merchant_id="merch_econ_zero", min_margin=0.0, max_discount=25.0),
        products=[
            InitialProductSpec(
                product_id="prod_econ_zero_01",
                name="Zero Margin Backpack",
                sku="SKU-ZERO-01",
                category="travel_backpack",
                price_paise=300000,
                cost_paise=300000,  # Exactly 0% gross margin: Price == COGS
                inventory_quantity=20,
                attributes={"laptop_size": 15.0},
                is_active=True,
            )
        ],
        active_policy_id="cand_econ_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    payment_status_override="captured",
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="econ_zero_boundary_success",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="boundary",
            field_path="boundary_status",
            operator="eq",
            expected_value="EXECUTION_COMPLETED",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Phase 9.2 boundary authorization must complete normally",
        ),
        BenchmarkExpectation(
            expectation_id="econ_zero_payment_success",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="outcome",
            field_path="outcome_status",
            operator="eq",
            expected_value="PAYMENT_SUCCESS",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Outcome status must be PAYMENT_SUCCESS",
        ),
        BenchmarkExpectation(
            expectation_id="econ_zero_reward_exactly_zero",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="eq",
            expected_value=0,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Reward contribution must be exactly 0 paise when Revenue equals COGS",
        ),
        BenchmarkExpectation(
            expectation_id="econ_zero_learning_eligible",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="outcome",
            field_path="learning_eligible",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
            description="Zero-contribution purchase is learning-eligible (retained in denominator)",
        ),
        BenchmarkExpectation(
            expectation_id="econ_zero_memory_total_zero",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="memory",
            field_path="total_observed_contribution_paise",
            operator="eq",
            expected_value=0,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Policy memory aggregate must reflect 0 contribution, not positive inflation",
        ),
    ],
    tags=["contribution", "zero_reward", "margin", "closed_loop"],
)


# ==============================================================================
# 2. SCENARIO 2: SIGNED NEGATIVE CONTRIBUTION PRESERVED (Revenue < COGS)
# ==============================================================================
SCENARIO_ECON_NEGATIVE_CONTRIBUTION = BenchmarkScenario(
    scenario_id="ECON_NEGATIVE_CONTRIBUTION_PRESERVED",
    description="Predatory/loss-leader purchase where Revenue < TotalCOGS; negative contribution must NOT be clipped to 0.",
    category=ScenarioCategory.ECONOMICS,
    merchant_id="merch_econ_neg",
    buyer_context=BuyerContextInput(
        raw_prompt="loss leader commuter backpack under 3000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_economic_merchant(merchant_id="merch_econ_neg", min_margin=-50.0, max_discount=0.0),
        products=[
            InitialProductSpec(
                product_id="prod_econ_neg_01",
                name="Loss Leader Backpack",
                sku="SKU-NEG-01",
                category="travel_backpack",
                price_paise=200000,
                cost_paise=201650,  # COGS exceeds price by 1,650 paise (₹16.50)
                inventory_quantity=10,
                attributes={"laptop_size": 14.0},
                is_active=True,
            )
        ],
        active_policy_id="cand_econ_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    payment_status_override="captured",
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="econ_neg_boundary_ok",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="boundary",
            field_path="boundary_status",
            operator="eq",
            expected_value="EXECUTION_COMPLETED",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Execution boundary passes for configured negative margin tolerance",
        ),
        BenchmarkExpectation(
            expectation_id="econ_neg_payment_success",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="outcome",
            field_path="outcome_status",
            operator="eq",
            expected_value="PAYMENT_SUCCESS",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Payment succeeds in test mode",
        ),
        BenchmarkExpectation(
            expectation_id="econ_neg_reward_signed",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="eq",
            expected_value=-1650,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Signed negative contribution (-1650 paise) must be preserved exactly without clipping",
        ),
        BenchmarkExpectation(
            expectation_id="econ_neg_strictly_negative",
            expectation_type=ExpectationType.RELATIONAL,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="lt",
            expected_value=0,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Reward must be strictly less than 0 paise",
        ),
        BenchmarkExpectation(
            expectation_id="econ_neg_memory_sum_negative",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="memory",
            field_path="total_observed_contribution_paise",
            operator="eq",
            expected_value=-1650,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Policy memory record preserves signed negative contribution",
        ),
    ],
    tags=["contribution", "negative_reward", "margin", "loss_leader"],
)


# ==============================================================================
# 3. SCENARIO 3: REVENUE != CONTRIBUTION SEPARATION
# ==============================================================================
SCENARIO_ECON_REVENUE_NOT_EQUAL_CONTRIBUTION = BenchmarkScenario(
    scenario_id="ECON_REVENUE_NOT_EQUAL_CONTRIBUTION",
    description="High-revenue low-margin purchase; proves the system never confuses gross revenue with contribution.",
    category=ScenarioCategory.ECONOMICS,
    merchant_id="merch_econ_rev_diff",
    buyer_context=BuyerContextInput(
        raw_prompt="premium luxury travel pack under 6000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_economic_merchant(merchant_id="merch_econ_rev_diff", min_margin=2.0, max_discount=10.0),
        products=[
            InitialProductSpec(
                product_id="prod_econ_high_rev",
                name="Luxury Expedition 50L",
                sku="SKU-LUX-01",
                category="travel_backpack",
                price_paise=500000,  # Revenue: ₹5,000
                cost_paise=480000,   # COGS: ₹4,800 -> Contribution: ₹200 (20,000 paise)
                inventory_quantity=15,
                attributes={"waterproof": True},
                is_active=True,
            )
        ],
        active_policy_id="cand_econ_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    payment_status_override="captured",
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="econ_rev_auth_amount",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="boundary",
            field_path="authorized_amount_paise",
            operator="eq",
            expected_value=500000,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Authorized order amount must match realized revenue (500000 paise)",
        ),
        BenchmarkExpectation(
            expectation_id="econ_rev_reward_differs_from_revenue",
            expectation_type=ExpectationType.RELATIONAL,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="ne",
            expected_value=500000,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Observed reward contribution must NOT equal gross revenue",
        ),
        BenchmarkExpectation(
            expectation_id="econ_rev_exact_contribution",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="eq",
            expected_value=20000,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Observed reward contribution must equal net contribution (20000 paise)",
        ),
    ],
    tags=["revenue", "contribution", "accounting"],
)


# ==============================================================================
# 4. SCENARIO 4: BUNDLE MULTI-ITEM COGS MATH
# ==============================================================================
SCENARIO_ECON_BUNDLE_MULTI_ITEM_MATH = BenchmarkScenario(
    scenario_id="ECON_BUNDLE_MULTI_ITEM_MATH",
    description="Multi-item basket; asserts TotalCOGS is the exact sum of item COGS and discount is applied once.",
    category=ScenarioCategory.ECONOMICS,
    merchant_id="merch_econ_bundle",
    buyer_context=BuyerContextInput(
        raw_prompt="travel pack with daypack combo under 6000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_economic_merchant(merchant_id="merch_econ_bundle", min_margin=20.0, max_discount=25.0),
        products=[
            InitialProductSpec(
                product_id="prod_econ_bundle_main",
                name="Main Trek Pack 45L",
                sku="SKU-BND-01",
                category="travel_backpack",
                price_paise=350000,
                cost_paise=180000,
                inventory_quantity=20,
                attributes={"laptop_size": 16.0},
                is_active=True,
            ),
            InitialProductSpec(
                product_id="prod_econ_bundle_sub",
                name="Detachable Daypack 15L",
                sku="SKU-BND-02",
                category="travel_backpack",
                price_paise=150000,
                cost_paise=80000,
                inventory_quantity=20,
                attributes={"laptop_size": 13.0},
                is_active=True,
            ),
        ],
        active_policy_id="cand_econ_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    payment_status_override="captured",
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="econ_bundle_boundary_ok",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="boundary",
            field_path="boundary_status",
            operator="eq",
            expected_value="EXECUTION_COMPLETED",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Boundary execution succeeds for bundle proposal",
        ),
        BenchmarkExpectation(
            expectation_id="econ_bundle_positive_reward",
            expectation_type=ExpectationType.RELATIONAL,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="gt",
            expected_value=0,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Bundle contribution must be strictly positive",
        ),
    ],
    tags=["bundle", "cogs", "quantity"],
)


# ==============================================================================
# 5. SCENARIO 5: MULTI-UNIT QUANTITY SCALING
# ==============================================================================
SCENARIO_ECON_MULTI_UNIT_QUANTITY = BenchmarkScenario(
    scenario_id="ECON_MULTI_UNIT_QUANTITY_SCALING",
    description="Multi-unit purchase (quantity = 2); TotalCOGS must scale strictly as UnitCost * Quantity.",
    category=ScenarioCategory.ECONOMICS,
    merchant_id="merch_econ_multi_qty",
    buyer_context=BuyerContextInput(
        raw_prompt="need 2 commuter backpacks under 8000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_economic_merchant(merchant_id="merch_econ_multi_qty", min_margin=20.0, max_discount=0.0),
        products=[
            InitialProductSpec(
                product_id="prod_econ_multi_01",
                name="Campus Commuter 25L",
                sku="SKU-QTY-01",
                category="travel_backpack",
                price_paise=300000,  # ₹3,000 unit price
                cost_paise=150000,   # ₹1,500 unit cost
                inventory_quantity=20,
                attributes={"laptop_size": 15.6},
                is_active=True,
            )
        ],
        active_policy_id="cand_econ_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    payment_status_override="captured",
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="econ_qty_authorized_amount",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="boundary",
            field_path="authorized_amount_paise",
            operator="eq",
            expected_value=600000,  # 300,000 * 2 = 600,000 paise
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Authorized amount must reflect quantity 2 (600,000 paise)",
        ),
        BenchmarkExpectation(
            expectation_id="econ_qty_reward_scaled",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="eq",
            expected_value=300000,  # (300,000 - 150,000) * 2 = 300,000 paise
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Reward contribution must reflect 2 units of margin (300,000 paise)",
        ),
    ],
    tags=["quantity", "cogs", "scaling"],
)


# ==============================================================================
# 6. SCENARIO 6: INVENTORY SAFETY BARRIER (ECONOMIC VALIDITY != EXECUTION)
# ==============================================================================
SCENARIO_ECON_INVENTORY_BARRIER = BenchmarkScenario(
    scenario_id="ECON_INVENTORY_SAFETY_BARRIER",
    description="Economically attractive candidate is rejected at boundary due to stockout race condition; creates no side effect.",
    category=ScenarioCategory.ECONOMICS,
    merchant_id="merch_econ_stockout",
    buyer_context=BuyerContextInput(
        raw_prompt="travel pack under 5000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_economic_merchant(merchant_id="merch_econ_stockout", min_margin=15.0, max_discount=25.0),
        products=[
            InitialProductSpec(
                product_id="prod_econ_stock_01",
                name="Trekker Pro 40L",
                sku="SKU-STK-01",
                category="travel_backpack",
                price_paise=400000,
                cost_paise=200000,
                inventory_quantity=5,
                attributes={"laptop_size": 16.0},
                is_active=True,
            )
        ],
        active_policy_id="cand_econ_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    input_overrides={"mutate_inventory_before_execution": 0},
    simulate_payment=True,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="econ_stock_stale_rejected",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="boundary",
            field_path="stale_state_rejected",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.SAFETY_FAILURE,
            description="Boundary must detect depleted inventory and reject execution",
        ),
        BenchmarkExpectation(
            expectation_id="econ_stock_no_order",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="boundary",
            field_path="order_id",
            operator="is_none",
            expected_value=None,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Stockout rejection must not create an authoritative Order",
        ),
        BenchmarkExpectation(
            expectation_id="econ_stock_no_outcome",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="outcome",
            field_path="outcome_id",
            operator="is_none",
            expected_value=None,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Stockout rejection must not create an Outcome record",
        ),
        BenchmarkExpectation(
            expectation_id="econ_stock_no_memory",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="memory",
            field_path="memory_count",
            operator="eq",
            expected_value=0,
            failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
            description="Stockout rejection must not generate learning memory",
        ),
    ],
    tags=["inventory", "safety", "no_side_effects"],
)


# ==============================================================================
# 7. SCENARIO 7: NO_OFFER BASELINE COMPARISON
# ==============================================================================
SCENARIO_ECON_NO_OFFER_BASELINE = BenchmarkScenario(
    scenario_id="ECON_NO_OFFER_EQUAL_BASELINE",
    description="When candidate predicted contribution is <= NO_OFFER reserve baseline, NO_OFFER must be selected.",
    category=ScenarioCategory.ECONOMICS,
    merchant_id="merch_econ_no_offer",
    buyer_context=BuyerContextInput(
        raw_prompt="product with no catalog match",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_economic_merchant(merchant_id="merch_econ_no_offer"),
        products=[],  # Empty catalog forces NO_OFFER
        active_policy_id="cand_base_no_offer",
    ),
    execution_mode=BenchmarkExecutionMode.DECISION_ONLY,
    simulate_payment=False,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="econ_no_offer_strategy",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="decision",
            field_path="selected_strategy",
            operator="eq",
            expected_value="NO_OFFER",
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Deterministic selection must choose NO_OFFER strategy",
        ),
        BenchmarkExpectation(
            expectation_id="econ_no_offer_unauthorized",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="decision",
            field_path="execution_authorized_9_1",
            operator="eq",
            expected_value=False,
            failure_class=FailureClass.SAFETY_FAILURE,
            description="NO_OFFER selection cannot authorize execution",
        ),
    ],
    tags=["baseline", "no_offer", "selection"],
)


# ==============================================================================
# 8. SCENARIO 8: EXPECTED VS OBSERVED DIVERGENCE
# ==============================================================================
SCENARIO_ECON_EXPECTED_VS_OBSERVED = BenchmarkScenario(
    scenario_id="ECON_EXPECTED_VS_OBSERVED_DIVERGENCE",
    description="Payment failure diverges observed economics (0 paise) from decision expectation (>0); system does not overwrite one with other.",
    category=ScenarioCategory.ECONOMICS,
    merchant_id="merch_econ_div",
    buyer_context=BuyerContextInput(
        raw_prompt="commuter backpack under 4000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_economic_merchant(merchant_id="merch_econ_div", min_margin=20.0),
        products=[
            InitialProductSpec(
                product_id="prod_econ_div_01",
                name="Commuter Everyday 20L",
                sku="SKU-DIV-01",
                category="travel_backpack",
                price_paise=350000,
                cost_paise=200000,
                inventory_quantity=10,
                attributes={"laptop_size": 15.0},
                is_active=True,
            )
        ],
        active_policy_id="cand_econ_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=True,
    payment_status_override="failed",
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="econ_div_boundary_ok",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="boundary",
            field_path="boundary_status",
            operator="eq",
            expected_value="EXECUTION_COMPLETED",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Boundary authorization completes before payment failure",
        ),
        BenchmarkExpectation(
            expectation_id="econ_div_outcome_failed",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="outcome",
            field_path="outcome_status",
            operator="eq",
            expected_value="PAYMENT_FAILED",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Outcome status is PAYMENT_FAILED",
        ),
        BenchmarkExpectation(
            expectation_id="econ_div_observed_zero",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="outcome",
            field_path="reward_contribution_paise",
            operator="eq",
            expected_value=0,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Realized reward contribution is 0 paise despite positive expected contribution",
        ),
        BenchmarkExpectation(
            expectation_id="econ_div_memory_zero",
            expectation_type=ExpectationType.EXACT_VALUE,
            target_domain="memory",
            field_path="total_observed_contribution_paise",
            operator="eq",
            expected_value=0,
            failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
            description="Memory preserves observed 0 reward, does not record decision-time expectation",
        ),
    ],
    tags=["expected_vs_observed", "prediction", "outcome"],
)


# ==============================================================================
# 9. SCENARIO 9: POLICY REJECTION CREATES ZERO ECONOMIC SIDE EFFECT
# ==============================================================================
SCENARIO_ECON_REJECTION_ZERO_SIDE_EFFECTS = BenchmarkScenario(
    scenario_id="ECON_REJECTION_ZERO_SIDE_EFFECTS",
    description="Commercial candidate breaching margin floor is rejected; zero orders, payments, memories, or model changes created.",
    category=ScenarioCategory.ECONOMICS,
    merchant_id="merch_econ_floor_breach",
    buyer_context=BuyerContextInput(
        raw_prompt="travel pack under 3000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_economic_merchant(merchant_id="merch_econ_floor_breach", min_margin=40.0, max_discount=10.0),
        products=[
            InitialProductSpec(
                product_id="prod_econ_breach_01",
                name="Below Floor Backpack",
                sku="SKU-BRC-01",
                category="travel_backpack",
                price_paise=100000,
                cost_paise=90000,  # 10% margin violates 40% floor
                inventory_quantity=10,
                attributes={"laptop_size": 14.0},
                is_active=True,
            )
        ],
        active_policy_id="cand_base_no_offer",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    simulate_payment=False,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="econ_brc_no_offer_selected",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="decision",
            field_path="selected_strategy",
            operator="eq",
            expected_value="NO_OFFER",
            failure_class=FailureClass.SAFETY_FAILURE,
            description="Validation rejection must force NO_OFFER selection",
        ),
        BenchmarkExpectation(
            expectation_id="econ_brc_no_execution_id",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="boundary",
            field_path="execution_id",
            operator="is_none",
            expected_value=None,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Rejection must not create an execution record",
        ),
        BenchmarkExpectation(
            expectation_id="econ_brc_no_order_id",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="boundary",
            field_path="order_id",
            operator="is_none",
            expected_value=None,
            failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
            description="Rejection must not create an order",
        ),
        BenchmarkExpectation(
            expectation_id="econ_brc_memory_zero",
            expectation_type=ExpectationType.NO_SIDE_EFFECT,
            target_domain="memory",
            field_path="memory_count",
            operator="eq",
            expected_value=0,
            failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
            description="Rejection must not create policy memory records",
        ),
    ],
    tags=["margin", "rejection", "no_side_effects"],
)


# ==============================================================================
# 10. SCENARIO 10: PROMOTION ECONOMIC GATING
# ==============================================================================
SCENARIO_ECON_PROMOTION_GATING = BenchmarkScenario(
    scenario_id="ECON_PROMOTION_ECONOMIC_GATE",
    description="Candidate policy with positive economics cannot promote without sufficient sample governance.",
    category=ScenarioCategory.ECONOMICS,
    merchant_id="merch_econ_promo",
    buyer_context=BuyerContextInput(
        raw_prompt="commuter backpack under 4000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_economic_merchant(merchant_id="merch_econ_promo"),
        products=[
            InitialProductSpec(
                product_id="prod_econ_promo_01",
                name="Sample Pack 20L",
                sku="SKU-PRM-01",
                category="travel_backpack",
                price_paise=300000,
                cost_paise=150000,
                inventory_quantity=20,
                attributes={"laptop_size": 15.0},
                is_active=True,
            )
        ],
        active_policy_id="cand_econ_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    input_overrides={
        "attempt_lifecycle_promotion": True,
        "promotion_target_policy_id": "cand_econ_treatment",
    },
    simulate_payment=True,
    payment_status_override="captured",
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="econ_prm_status_insufficient",
            expectation_type=ExpectationType.INVARIANT,
            target_domain="lifecycle",
            field_path="promotion_status",
            operator="in",
            expected_value=["INSUFFICIENT_EVIDENCE", "NOT_ELIGIBLE"],
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Promotion must be rejected due to insufficient evidence sample size",
        ),
        BenchmarkExpectation(
            expectation_id="econ_prm_active_unchanged",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="lifecycle",
            field_path="active_policy_id",
            operator="eq",
            expected_value="cand_econ_base",
            failure_class=FailureClass.LIFECYCLE_FAILURE,
            description="Active policy must remain cand_econ_base and not be mutated by promotion attempt",
        ),
    ],
    tags=["promotion", "lifecycle", "governance"],
)


# ==============================================================================
# 11. SCENARIO 11: CROSS-MERCHANT ECONOMIC ISOLATION
# ==============================================================================
SCENARIO_ECON_CROSS_MERCHANT_ISOLATION = BenchmarkScenario(
    scenario_id="ECON_CROSS_MERCHANT_ECONOMIC_ISOLATION",
    description="Cross-tenant execution attempt; attacker merchant cannot execute or mutate victim merchant economics.",
    category=ScenarioCategory.ECONOMICS,
    merchant_id="merch_econ_victim",
    buyer_context=BuyerContextInput(
        raw_prompt="travel pack under 5000",
    ),
    initial_state=InitialStateSpec(
        merchant=_create_economic_merchant(merchant_id="merch_econ_victim"),
        products=[
            InitialProductSpec(
                product_id="prod_econ_vic_01",
                name="Victim Pack 30L",
                sku="SKU-VIC-01",
                category="travel_backpack",
                price_paise=400000,
                cost_paise=200000,
                inventory_quantity=20,
                attributes={"laptop_size": 15.0},
                is_active=True,
            )
        ],
        active_policy_id="cand_econ_base",
    ),
    execution_mode=BenchmarkExecutionMode.FULL_CLOSED_LOOP,
    input_overrides={
        "test_cross_tenant_attack": True,
        "attacker_merchant_id": "merch_econ_attacker",
    },
    simulate_payment=True,
    expected_invariants=[
        BenchmarkExpectation(
            expectation_id="econ_iso_cross_tenant_rejected",
            expectation_type=ExpectationType.ISOLATION,
            target_domain="security",
            field_path="cross_tenant_rejected",
            operator="eq",
            expected_value=True,
            failure_class=FailureClass.TENANT_ISOLATION_FAILURE,
            description="Cross-tenant execution attempt must be strictly rejected with tenant violation error",
        ),
        BenchmarkExpectation(
            expectation_id="econ_iso_victim_order_intact",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="boundary",
            field_path="boundary_status",
            operator="eq",
            expected_value="EXECUTION_COMPLETED",
            failure_class=FailureClass.TENANT_ISOLATION_FAILURE,
            description="Legitimate victim execution completes without cross-tenant mutation",
        ),
    ],
    tags=["tenant", "isolation", "security"],
)


ECONOMIC_SCENARIOS: List[BenchmarkScenario] = [
    SCENARIO_ECON_ZERO_CONTRIBUTION,
    SCENARIO_ECON_NEGATIVE_CONTRIBUTION,
    SCENARIO_ECON_REVENUE_NOT_EQUAL_CONTRIBUTION,
    SCENARIO_ECON_BUNDLE_MULTI_ITEM_MATH,
    SCENARIO_ECON_MULTI_UNIT_QUANTITY,
    SCENARIO_ECON_INVENTORY_BARRIER,
    SCENARIO_ECON_NO_OFFER_BASELINE,
    SCENARIO_ECON_EXPECTED_VS_OBSERVED,
    SCENARIO_ECON_REJECTION_ZERO_SIDE_EFFECTS,
    SCENARIO_ECON_PROMOTION_GATING,
    SCENARIO_ECON_CROSS_MERCHANT_ISOLATION,
]


def register_economic_scenarios():
    """Register all 11 economic scenarios into BenchmarkRegistry."""
    from services.benchmark.registry import BenchmarkRegistry
    for scen in ECONOMIC_SCENARIOS:
        BenchmarkRegistry.register(scen)


register_economic_scenarios()
