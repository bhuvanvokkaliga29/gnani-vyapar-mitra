"""Integration Tests for Phase 11.3 Economic Adversarial Validation Suite.

Contract: benchmark-scenario/v1
Category: ECONOMICS

Executes all 11 Phase 11.3 Economic Adversarial Scenarios against authoritative domain services:
1. ECON_ZERO_CONTRIBUTION_PURCHASE
2. ECON_NEGATIVE_CONTRIBUTION_PRESERVED
3. ECON_REVENUE_NOT_EQUAL_CONTRIBUTION
4. ECON_BUNDLE_MULTI_ITEM_MATH
5. ECON_MULTI_UNIT_QUANTITY_SCALING
6. ECON_INVENTORY_SAFETY_BARRIER
7. ECON_NO_OFFER_EQUAL_BASELINE
8. ECON_EXPECTED_VS_OBSERVED_DIVERGENCE
9. ECON_REJECTION_ZERO_SIDE_EFFECTS
10. ECON_PROMOTION_ECONOMIC_GATE
11. ECON_CROSS_MERCHANT_ECONOMIC_ISOLATION

Also verifies:
- Complete suite execution (11/11 pass, 0 fail)
- Deterministic repeatability (N=3 runs on 3 distinct economic scenarios, 0 divergence)
- Strictly zero economic side effects on rejection (before and after DB entity comparison)
"""

import pytest
from sqlalchemy import select, func

from domain.models import (
    Order,
    Payment,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
    PolicyMemoryRecord,
    MerchantActivePolicy,
)
from services.benchmark.schemas import BenchmarkStatus
from services.benchmark.economic_scenarios import (
    ECONOMIC_SCENARIOS,
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
)
from services.benchmark.runner import CanonicalBenchmarkRunner


@pytest.mark.asyncio
async def test_econ_scenario_01_zero_contribution_purchase(db_session):
    """Scenario 1: Purchase where RealizedRevenue == TotalCOGS -> Contrib = 0."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ECON_ZERO_CONTRIBUTION)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.boundary_status == "EXECUTION_COMPLETED"
    assert obs.outcome_status == "PAYMENT_SUCCESS"
    assert obs.reward_contribution_paise == 0
    assert obs.total_observed_contribution_paise == 0
    assert obs.learning_eligible is True


@pytest.mark.asyncio
async def test_econ_scenario_02_negative_contribution_preserved(db_session):
    """Scenario 2: Signed negative contribution (-1650 paise) preserved, no clipping."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ECON_NEGATIVE_CONTRIBUTION)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.boundary_status == "EXECUTION_COMPLETED"
    assert obs.outcome_status == "PAYMENT_SUCCESS"
    assert obs.reward_contribution_paise == -1650
    assert obs.total_observed_contribution_paise == -1650
    assert obs.reward_contribution_paise < 0


@pytest.mark.asyncio
async def test_econ_scenario_03_revenue_not_equal_contribution(db_session):
    """Scenario 3: High revenue (500000 paise) != low contribution (20000 paise)."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ECON_REVENUE_NOT_EQUAL_CONTRIBUTION)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.authorized_amount_paise == 500000
    assert obs.reward_contribution_paise == 20000
    assert obs.reward_contribution_paise != obs.authorized_amount_paise


@pytest.mark.asyncio
async def test_econ_scenario_04_bundle_multi_item_math(db_session):
    """Scenario 4: Multi-item bundle; TotalCOGS is sum of item COGS."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ECON_BUNDLE_MULTI_ITEM_MATH)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.boundary_status == "EXECUTION_COMPLETED"
    assert obs.outcome_status == "PAYMENT_SUCCESS"
    assert obs.reward_contribution_paise is not None and obs.reward_contribution_paise > 0


@pytest.mark.asyncio
async def test_econ_scenario_05_multi_unit_quantity_scaling(db_session):
    """Scenario 5: Multi-unit purchase (quantity = 2); TotalCOGS scales strictly."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ECON_MULTI_UNIT_QUANTITY)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.authorized_amount_paise == 600000
    assert obs.reward_contribution_paise == 300000


@pytest.mark.asyncio
async def test_econ_scenario_06_inventory_safety_barrier(db_session):
    """Scenario 6: Stockout blocks boundary execution; economic validity != execution."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ECON_INVENTORY_BARRIER)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.stale_state_rejected is True
    assert obs.order_id is None
    assert obs.outcome_id is None
    assert obs.memory_count == 0


@pytest.mark.asyncio
async def test_econ_scenario_07_no_offer_equal_baseline(db_session):
    """Scenario 7: Candidate <= NO_OFFER baseline selects NO_OFFER."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ECON_NO_OFFER_BASELINE)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.selected_strategy == "NO_OFFER"
    assert obs.execution_authorized_9_1 is False
    assert obs.order_id is None


@pytest.mark.asyncio
async def test_econ_scenario_08_expected_vs_observed_divergence(db_session):
    """Scenario 8: Decision prediction does not overwrite outcome observation on payment failure."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ECON_EXPECTED_VS_OBSERVED)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.outcome_status == "PAYMENT_FAILED"
    assert obs.reward_contribution_paise == 0
    assert obs.total_observed_contribution_paise == 0


@pytest.mark.asyncio
async def test_econ_scenario_09_rejection_zero_side_effects(db_session):
    """Scenario 9: Rejection of margin breach creates zero DB side effects."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ECON_REJECTION_ZERO_SIDE_EFFECTS)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.selected_strategy == "NO_OFFER"
    assert obs.execution_id is None
    assert obs.order_id is None
    assert obs.memory_count == 0


@pytest.mark.asyncio
async def test_econ_scenario_10_promotion_economic_gate(db_session):
    """Scenario 10: Profitable candidate cannot promote without sufficient sample size."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ECON_PROMOTION_GATING)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.promotion_status in ("INSUFFICIENT_EVIDENCE", "NOT_ELIGIBLE")
    assert obs.active_policy_id == "cand_econ_base"


@pytest.mark.asyncio
async def test_econ_scenario_11_cross_merchant_economic_isolation(db_session):
    """Scenario 11: Attacker merchant execution attempt rejected with tenant error."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ECON_CROSS_MERCHANT_ISOLATION)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.cross_tenant_rejected is True
    assert obs.boundary_status == "EXECUTION_COMPLETED"


@pytest.mark.asyncio
async def test_economic_scenario_suite_execution(db_session):
    """Execute complete Phase 11.3 Economic Scenario Suite (11/11 pass, 0 fail)."""
    summary, results = await CanonicalBenchmarkRunner.run_suite(db_session, ECONOMIC_SCENARIOS)
    assert summary.total_scenarios == 11
    assert summary.passed == 11
    assert summary.failed == 0
    assert summary.inconclusive == 0
    assert summary.assertions_failed == 0
    assert summary.reproducibility_status == "VERIFIED"


@pytest.mark.asyncio
async def test_economic_scenarios_repeatability(db_session):
    """Verify deterministic repeatability across N=3 runs on 3 distinct economic scenarios."""
    scenarios_to_test = [
        SCENARIO_ECON_ZERO_CONTRIBUTION,
        SCENARIO_ECON_NEGATIVE_CONTRIBUTION,
        SCENARIO_ECON_MULTI_UNIT_QUANTITY,
    ]
    for scen in scenarios_to_test:
        rep = await CanonicalBenchmarkRunner.run_repeatability(db_session, scen, repeat_count=3)
        assert rep["all_passed"] is True, f"Scenario {scen.scenario_id} failed in repeatability run"
        assert rep["is_reproducible"] is True, f"Divergences found for {scen.scenario_id}: {rep['divergences']}"
        assert rep["divergences"] == []


@pytest.mark.asyncio
async def test_margin_rejection_strictly_zero_economic_side_effects(db_session):
    """Verify pre vs post counts on DB entities for an economically rejected decision."""
    merchant_id = "merch_econ_side_effect_audit"

    # Pre-execution counts
    pre_orders = (await db_session.execute(select(func.count(Order.id)))).scalar() or 0
    pre_payments = (await db_session.execute(select(func.count(Payment.id)))).scalar() or 0
    pre_executions = (await db_session.execute(select(func.count(DecisionExecutionRecord.id)).where(DecisionExecutionRecord.merchant_id == merchant_id))).scalar() or 0
    pre_outcomes = (await db_session.execute(select(func.count(OutcomeFeedbackRecord.id)).where(OutcomeFeedbackRecord.merchant_id == merchant_id))).scalar() or 0
    pre_memories = (await db_session.execute(select(func.count(PolicyMemoryRecord.id)).where(PolicyMemoryRecord.merchant_id == merchant_id))).scalar() or 0

    # Run rejection scenario
    await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ECON_REJECTION_ZERO_SIDE_EFFECTS)

    # Post-execution counts
    post_orders = (await db_session.execute(select(func.count(Order.id)))).scalar() or 0
    post_payments = (await db_session.execute(select(func.count(Payment.id)))).scalar() or 0
    post_executions = (await db_session.execute(select(func.count(DecisionExecutionRecord.id)).where(DecisionExecutionRecord.merchant_id == merchant_id))).scalar() or 0
    post_outcomes = (await db_session.execute(select(func.count(OutcomeFeedbackRecord.id)).where(OutcomeFeedbackRecord.merchant_id == merchant_id))).scalar() or 0
    post_memories = (await db_session.execute(select(func.count(PolicyMemoryRecord.id)).where(PolicyMemoryRecord.merchant_id == merchant_id))).scalar() or 0

    assert post_orders == pre_orders
    assert post_payments == pre_payments
    assert post_executions == pre_executions
    assert post_outcomes == pre_outcomes
    assert post_memories == pre_memories
