"""Integration Tests for Phase 11.2 Golden Adversarial Validation Suite.

Executes all 10 Golden Scenarios against real authoritative domain services:
1. GOLDEN_PAYMENT_FAILURE_TRUTH
2. GOLDEN_NO_OFFER_SHORT_CIRCUIT
3. GOLDEN_SAFETY_REJECTION_BLOCK
4. GOLDEN_STALE_STATE_REJECTION
5. GOLDEN_DUPLICATE_OUTCOME_ONCE
6. GOLDEN_LUCKY_PURCHASE_GATE
7. GOLDEN_LEARNING_NO_PROMOTION
8. GOLDEN_MERCHANT_BOUNDARY_ATTACK
9. GOLDEN_NEGATIVE_CONTRIBUTION
10. GOLDEN_EXECUTION_FAILURE_SHIELD

Also verifies:
- Suite execution (all 10 pass, 0 fail)
- Deterministic repeatability ($N=3$ runs on 3 distinct scenarios)
- Controlled failure injection (injected assertion mismatch correctly reports FAIL)
- Zero secret leakage in artifacts
"""

import os
import tempfile
import pytest
from copy import deepcopy

from services.benchmark.schemas import (
    BenchmarkStatus,
    FailureClass,
    ExpectationType,
    BenchmarkExpectation,
)
from services.benchmark.golden_scenarios import (
    GOLDEN_SCENARIO_SUITE,
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
)
from services.benchmark.runner import CanonicalBenchmarkRunner
from services.benchmark.reporter import BenchmarkReporter


@pytest.mark.asyncio
async def test_golden_scenario_01_payment_failure_truth(db_session):
    """Scenario 1: Payment failure must not become positive learning."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_1_PAYMENT_FAILURE_TRUTH)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.boundary_status == "EXECUTION_COMPLETED"
    assert obs.outcome_status == "PAYMENT_FAILED"
    assert obs.reward_contribution_paise == 0
    assert obs.learning_eligible is True


@pytest.mark.asyncio
async def test_golden_scenario_02_no_offer_short_circuit(db_session):
    """Scenario 2: Unrealistic buyer context triggers NO_OFFER short-circuit without boundary."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_2_NO_OFFER_SHORT_CIRCUIT)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.selected_strategy == "NO_OFFER"
    assert obs.boundary_status in [None, "NOT_REQUESTED"]
    assert obs.order_id is None


@pytest.mark.asyncio
async def test_golden_scenario_03_safety_rejection_block(db_session):
    """Scenario 3: Excessive discount fails safety margin clearance and blocks boundary execution."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_3_SAFETY_REJECTION_BLOCK)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.boundary_status in [None, "NOT_REQUESTED"]
    assert obs.order_id is None


@pytest.mark.asyncio
async def test_golden_scenario_04_stale_state_rejection(db_session):
    """Scenario 4: Inventory zeroed out before boundary execution triggers stale state rejection."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_4_STALE_STATE_REJECTION)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.stale_state_rejected is True
    assert obs.boundary_status == "SAFETY_REJECTED"
    assert obs.order_id is None


@pytest.mark.asyncio
async def test_golden_scenario_05_duplicate_outcome_once(db_session):
    """Scenario 5: Replay of outcome feedback is detected and recorded exactly once."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_5_DUPLICATE_OUTCOME_ONCE)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.is_duplicate_outcome is True
    assert obs.outcome_status == "PAYMENT_SUCCESS"


@pytest.mark.asyncio
async def test_golden_scenario_06_lucky_purchase_gate(db_session):
    """Scenario 6: Single lucky transaction cannot bypass sample size and confidence gates."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_6_LUCKY_PURCHASE_GATE)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.promotion_status in ["NOT_ELIGIBLE", "INSUFFICIENT_EVIDENCE", "REJECTED"]
    assert obs.promotion_failure_code in [
        "INSUFFICIENT_SAMPLE_SIZE",
        "SAMPLE_SIZE_INSUFFICIENT",
        "INSUFFICIENT_DATA",
        "MIN_SAMPLES_NOT_MET",
        "EVIDENCE_FIREWALL_ACTIVE",
    ]


@pytest.mark.asyncio
async def test_golden_scenario_07_learning_no_promotion(db_session):
    """Scenario 7: Eligible learning updates memory but does not mutate active baseline policy."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_7_LEARNING_NO_PROMOTION)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.learning_eligible is True
    assert obs.active_policy_id == "cand_golden_base"
    assert obs.promotion_status in [None, "NOT_REQUESTED"]


@pytest.mark.asyncio
async def test_golden_scenario_08_merchant_boundary_attack(db_session):
    """Scenario 8: Cross-tenant foreign product execution is rejected at the security boundary."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_8_MERCHANT_BOUNDARY_ATTACK)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.cross_tenant_rejected is True
    assert obs.merchant_id == "merch_golden_victim"


@pytest.mark.asyncio
async def test_golden_scenario_09_negative_contribution(db_session):
    """Scenario 9: High cost structure yields verified negative net contribution."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_9_NEGATIVE_CONTRIBUTION)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.reward_contribution_paise < 0
    assert obs.outcome_status == "PAYMENT_SUCCESS"


@pytest.mark.asyncio
async def test_golden_scenario_10_execution_failure_shield(db_session):
    """Scenario 10: Razorpay creation failure shields downstream outcome and learning."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_10_EXECUTION_FAILURE_SHIELD)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs is not None
    assert obs.boundary_status == "POLICY_RETIRED"
    assert obs.order_id is None
    assert obs.outcome_status != "PAYMENT_SUCCESS"


@pytest.mark.asyncio
async def test_golden_suite_full_run_and_artifacts(db_session):
    """Suite Run: Run all 10 golden scenarios in sequence and verify 100% pass and artifact generation."""
    summary, results = await CanonicalBenchmarkRunner.run_suite(db_session, GOLDEN_SCENARIO_SUITE)
    
    for r in results:
        if r.status != BenchmarkStatus.PASS:
            for d in r.diagnostics:
                if not d.passed:
                    print(f"FAILED SCENARIO {r.scenario_id}: {d.message} (exp={d.expected}, obs={d.observed})")

    assert summary.total_scenarios == 10
    assert summary.passed == 10
    assert summary.failed == 0
    assert summary.inconclusive == 0
    assert summary.assertions_total > 20
    assert summary.reproducibility_status == "VERIFIED"
    assert len(results) == 10

    with tempfile.TemporaryDirectory() as tmp_dir:
        artifacts = BenchmarkReporter.save_run_artifacts(tmp_dir, summary, results)
        assert os.path.exists(artifacts["benchmark_summary"])
        assert os.path.exists(artifacts["scenario_results"])
        assert os.path.exists(artifacts["benchmark_run"])
        assert os.path.exists(artifacts["benchmark_run_report"])
        
        # Verify content hygiene in written artifacts
        with open(artifacts["benchmark_run"], "r") as f:
            content = f.read().lower()
            for forbidden in ["key_secret", "cogs_paise", "sk_live", "rzp_live"]:
                assert forbidden not in content, f"Leaked secret '{forbidden}' in benchmark_run"


@pytest.mark.asyncio
async def test_golden_scenarios_deterministic_repeatability(db_session):
    """Repeatability ($N=3$): Verify zero variance across multiple runs of diverse scenarios."""
    scenarios_to_repeat = [
        SCENARIO_1_PAYMENT_FAILURE_TRUTH,
        SCENARIO_4_STALE_STATE_REJECTION,
        SCENARIO_9_NEGATIVE_CONTRIBUTION,
    ]

    for scenario in scenarios_to_repeat:
        first_result = None
        for iteration in range(3):
            result = await CanonicalBenchmarkRunner.run_scenario(db_session, scenario)
            assert result.status == BenchmarkStatus.PASS, f"Scenario {scenario.scenario_id} failed on run {iteration}"
            assert result.assertions_failed == 0

            if first_result is None:
                first_result = result
            else:
                # Assert exact state invariance
                assert result.status == first_result.status
                assert result.observed_state.boundary_status == first_result.observed_state.boundary_status
                assert result.observed_state.outcome_status == first_result.observed_state.outcome_status
                assert result.observed_state.reward_contribution_paise == first_result.observed_state.reward_contribution_paise
                assert result.observed_state.learning_eligible == first_result.observed_state.learning_eligible


@pytest.mark.asyncio
async def test_golden_controlled_failure_injection(db_session):
    """Controlled Failure: An intentionally unsatisfied expectation must be classified as FAIL with diagnostic."""
    mutated_scenario = deepcopy(SCENARIO_1_PAYMENT_FAILURE_TRUTH)
    mutated_scenario.scenario_id = "MUTATED_FAILURE_INJECTION"
    # Inject an expectation that will certainly fail
    mutated_scenario.expected_invariants.append(
        BenchmarkExpectation(
            expectation_id="injected_impossible_status",
            expectation_type=ExpectationType.EXACT_STATE,
            target_domain="boundary",
            field_path="boundary_status",
            operator="eq",
            expected_value="IMPOSSIBLE_STATUS_FOR_TEST",
            failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
            description="Intentionally impossible boundary status to verify failure reporting",
        )
    )

    result = await CanonicalBenchmarkRunner.run_scenario(db_session, mutated_scenario)
    assert result.status == BenchmarkStatus.FAIL
    assert result.assertions_failed >= 1
    assert any(d.failure_class == FailureClass.EXPECTED_STATE_MISMATCH for d in result.diagnostics if not d.passed)
    assert len(result.diagnostics) >= 1

    # Verify diagnostic specifics
    diag = next(d for d in result.diagnostics if d.expectation_id == "injected_impossible_status")
    assert diag.passed is False
    assert diag.field_path == "boundary_status"
    assert diag.expected == "IMPOSSIBLE_STATUS_FOR_TEST"
    assert diag.observed == "EXECUTION_COMPLETED"
