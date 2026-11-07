"""Unit Tests for Phase 11.1 Canonical Benchmark Harness.

Covers all Phase 11.1 verification requirements (A through Q):
A. scenario schema validation
B. result schema validation
C. scenario registry works
D. single scenario execution works
E. suite execution works
F. isolated state between scenarios
G. explicit initial state is respected
H. deterministic seed replay works
I. result artifact generation works
J. failure classification works
K. expected business assertion failure is reported correctly
L. harness/infrastructure failure is not disguised as PASS
M. no secret leakage in artifacts
N. merchant scope is preserved
O. scenario execution and assertion counts are not confused
P. repeatability comparison works
Q. runner does not bypass authoritative domain services
"""

import os
import tempfile
import pytest
from pydantic import ValidationError
from sqlalchemy import select, func

from domain.models import (
    Merchant,
    Product,
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
    PolicyMemoryRecord,
)
from services.benchmark.schemas import (
    BENCHMARK_SCENARIO_VERSION,
    BENCHMARK_RESULT_VERSION,
    BENCHMARK_SUMMARY_VERSION,
    BenchmarkScenario,
    BenchmarkResult,
    BenchmarkSummary,
    BenchmarkStatus,
    ScenarioCategory,
    FailureClass,
    ExpectationType,
    BenchmarkExecutionMode,
    BenchmarkExpectation,
    BuyerContextInput,
    InitialStateSpec,
    InitialMerchantSpec,
    InitialProductSpec,
    ExpectedTerminalState,
    ObservedStateSnapshot,
)
from services.benchmark.registry import (
    BenchmarkRegistry,
    SCENARIO_SMOKE_HAPPY_PATH,
    SCENARIO_SMOKE_PAYMENT_FAILURE,
    SCENARIO_SMOKE_NO_OFFER,
    SCENARIO_SMOKE_REPLAY_IDEMPOTENCY,
)
from services.benchmark.observer import BenchmarkObserver
from services.benchmark.assertions import AssertionEvaluator
from services.benchmark.runner import CanonicalBenchmarkRunner
from services.benchmark.reporter import BenchmarkReporter
from services.razorpay.models import RazorpayOrderResponse
from services.razorpay.orders import RazorpayOrderService
import uuid


@pytest.fixture(autouse=True)
def mock_razorpay_order_calls(monkeypatch):
    """Hermetic unit test isolation: mock Razorpay order creation to avoid live network calls."""
    async def _mock_create_order(self, amount_paise: int, receipt: str, currency: str = "INR", notes=None, payment_capture=1):
        return RazorpayOrderResponse(
            id=f"order_mock_{uuid.uuid4().hex[:8]}",
            entity="order",
            amount=amount_paise,
            amount_paid=0,
            amount_due=amount_paise,
            currency=currency,
            receipt=receipt,
            status="created",
            attempts=0,
            notes=notes or {},
            created_at=1725364800
        )

    monkeypatch.setattr(RazorpayOrderService, "create_order", _mock_create_order)


# ==================== Test A: Scenario Schema Validation ====================

def test_a_scenario_schema_validation():
    """Requirement A: Validate that BenchmarkScenario strictly enforces schema and forbids extra fields."""
    valid = BenchmarkScenario(
        scenario_id="scen_test_valid",
        description="A valid test scenario",
        category=ScenarioCategory.DECISION,
        merchant_id="merch_test",
        buyer_context=BuyerContextInput(raw_prompt="travel pack"),
    )
    assert valid.scenario_id == "scen_test_valid"
    assert valid.scenario_version == BENCHMARK_SCENARIO_VERSION

    # Reject unvalidated extra fields
    with pytest.raises(ValidationError):
        BenchmarkScenario(
            scenario_id="scen_test_invalid",
            description="Invalid",
            category=ScenarioCategory.DECISION,
            merchant_id="merch_test",
            buyer_context=BuyerContextInput(raw_prompt="pack"),
            unauthorized_field="malicious_payload",  # Extra field
        )


# ==================== Test B: Result Schema Validation ====================

def test_b_result_schema_validation():
    """Requirement B: Validate that BenchmarkResult and BenchmarkSummary serialize and validate correctly."""
    from datetime import datetime, timezone

    result = BenchmarkResult(
        run_id="run_test_01",
        scenario_id="scen_test_valid",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        status=BenchmarkStatus.PASS,
        category=ScenarioCategory.DECISION,
        merchant_id="merch_test",
        seed=42,
        assertions_total=5,
        assertions_passed=5,
        assertions_failed=0,
        duration_ms=123.45,
    )
    assert result.status == BenchmarkStatus.PASS
    assert result.scenario_version == BENCHMARK_RESULT_VERSION

    summary = BenchmarkSummary(
        run_id="run_test_01",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        total_scenarios=1,
        passed=1,
        failed=0,
        inconclusive=0,
        assertions_total=5,
        assertions_passed=5,
        assertions_failed=0,
        duration_ms=123.45,
    )
    assert summary.summary_version == BENCHMARK_SUMMARY_VERSION
    assert summary.total_scenarios == 1


# ==================== Test C: Scenario Registry Works ====================

def test_c_scenario_registry_works():
    """Requirement C: Verify scenario registration, listing, category filtering, and retrieval."""
    scen = BenchmarkScenario(
        scenario_id="scen_reg_test_01",
        description="Registry test",
        category=ScenarioCategory.SAFETY,
        merchant_id="merch_test",
        buyer_context=BuyerContextInput(raw_prompt="pack"),
        tags=["unit_test", "reg_test"],
    )
    BenchmarkRegistry.register(scen)

    retrieved = BenchmarkRegistry.get("scen_reg_test_01")
    assert retrieved is not None
    assert retrieved.scenario_id == "scen_reg_test_01"

    safety_scenarios = BenchmarkRegistry.list_by_category(ScenarioCategory.SAFETY)
    assert any(s.scenario_id == "scen_reg_test_01" for s in safety_scenarios)

    tagged = BenchmarkRegistry.list_by_tag("unit_test")
    assert any(s.scenario_id == "scen_reg_test_01" for s in tagged)


# ==================== Test D: Single Scenario Execution ====================

@pytest.mark.asyncio
async def test_d_single_scenario_execution(db_session):
    """Requirement D: Run a single scenario through CanonicalBenchmarkRunner."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_SMOKE_HAPPY_PATH)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_total >= 5
    assert result.assertions_failed == 0
    assert result.observed_state is not None
    assert result.observed_state.decision_id is not None
    assert result.observed_state.boundary_status == "EXECUTION_COMPLETED"
    assert result.observed_state.outcome_status == "PAYMENT_SUCCESS"


# ==================== Test E: Suite Execution Works ====================

@pytest.mark.asyncio
async def test_e_suite_execution(db_session):
    """Requirement E: Run a suite of scenarios and verify aggregate summary accounting."""
    suite = [SCENARIO_SMOKE_HAPPY_PATH, SCENARIO_SMOKE_NO_OFFER]
    summary, results = await CanonicalBenchmarkRunner.run_suite(db_session, suite)

    assert summary.total_scenarios == 2
    assert summary.passed == 2
    assert summary.failed == 0
    assert summary.inconclusive == 0
    assert summary.assertions_total > 0
    assert len(results) == 2


# ==================== Test F: Isolated State Between Scenarios ====================

@pytest.mark.asyncio
async def test_f_isolated_state_between_scenarios(db_session):
    """Requirement F: Verify scenarios maintain state isolation without unintended memory carryover."""
    # First scenario creates memory records
    res1 = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_SMOKE_HAPPY_PATH)
    assert res1.observed_state.memory_count >= 1

    # Second scenario on a clean/different merchant should have 0 prior memory
    scen_isolated = BenchmarkScenario(
        scenario_id="scen_isolated_clean",
        description="Clean merchant scenario",
        category=ScenarioCategory.DECISION,
        merchant_id="merch_isolated_clean",
        buyer_context=BuyerContextInput(raw_prompt="travel pack under 5000"),
        initial_state=InitialStateSpec(
            merchant=InitialMerchantSpec(
                merchant_id="merch_isolated_clean",
                name="Isolated Clean Merchant",
            ),
            products=[
                InitialProductSpec(
                    product_id="prod_iso_01",
                    name="Isolated Pack",
                    sku="SKU-ISO-01",
                    category="travel_backpack",
                    price_paise=400000,
                    cost_paise=200000,
                )
            ],
            active_policy_id="cand_iso_base",
        ),
        execution_mode=BenchmarkExecutionMode.DECISION_ONLY,
        expected_invariants=[
            BenchmarkExpectation(
                expectation_id="iso_exp_no_prior_memory",
                expectation_type=ExpectationType.NO_SIDE_EFFECT,
                target_domain="memory",
                field_path="memory_count",
                operator="eq",
                expected_value=0,
                description="New merchant must start with strictly 0 policy memory records",
            )
        ],
    )
    res2 = await CanonicalBenchmarkRunner.run_scenario(db_session, scen_isolated)
    assert res2.status == BenchmarkStatus.PASS
    assert res2.observed_state.memory_count == 0


# ==================== Test G: Explicit Initial State is Respected ====================

@pytest.mark.asyncio
async def test_g_explicit_initial_state_respected(db_session):
    """Requirement G: Verify declarative initial state (merchant, products, active policy) is seeded accurately."""
    custom_scen = BenchmarkScenario(
        scenario_id="scen_custom_init",
        description="Custom initial state",
        category=ScenarioCategory.DECISION,
        merchant_id="merch_custom_setup",
        buyer_context=BuyerContextInput(raw_prompt="travel backpack under 5000"),
        initial_state=InitialStateSpec(
            merchant=InitialMerchantSpec(
                merchant_id="merch_custom_setup",
                name="Custom Merchant Inc",
                minimum_margin_percent=18.5,
            ),
            products=[
                InitialProductSpec(
                    product_id="prod_custom_setup_01",
                    name="Custom Setup Pack",
                    sku="SKU-CS-01",
                    category="travel_backpack",
                    price_paise=420000,
                    cost_paise=210000,
                )
            ],
            active_policy_id="cand_custom_base",
        ),
        execution_mode=BenchmarkExecutionMode.DECISION_ONLY,
    )
    await CanonicalBenchmarkRunner.run_scenario(db_session, custom_scen)

    # Check merchant
    merch = (await db_session.execute(select(Merchant).where(Merchant.id == "merch_custom_setup"))).scalar_one()
    assert merch.name == "Custom Merchant Inc"
    assert float(merch.minimum_margin_percent) == 18.5

    # Check product
    prod = (await db_session.execute(select(Product).where(Product.id == "prod_custom_setup_01"))).scalar_one()
    assert prod.name == "Custom Setup Pack"


# ==================== Test H: Deterministic Seed Replay Works ====================

@pytest.mark.asyncio
async def test_h_deterministic_seed_replay(db_session):
    """Requirement H: Verify running with identical seed and inputs produces deterministic business decisions."""
    res1 = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_SMOKE_HAPPY_PATH)
    res2 = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_SMOKE_HAPPY_PATH)

    assert res1.observed_state.selected_strategy == res2.observed_state.selected_strategy
    assert res1.observed_state.offered_price_paise == res2.observed_state.offered_price_paise
    assert res1.observed_state.boundary_status == res2.observed_state.boundary_status
    assert res1.observed_state.outcome_status == res2.observed_state.outcome_status
    assert res1.observed_state.reward_contribution_paise == res2.observed_state.reward_contribution_paise


# ==================== Test I: Result Artifact Generation Works ====================

@pytest.mark.asyncio
async def test_i_result_artifact_generation(db_session):
    """Requirement I: Verify generation of benchmark_run.json, scenario_results.json, and benchmark_run_report.md."""
    suite = [SCENARIO_SMOKE_HAPPY_PATH]
    summary, results = await CanonicalBenchmarkRunner.run_suite(db_session, suite)

    with tempfile.TemporaryDirectory() as tmp_dir:
        artifacts = BenchmarkReporter.save_run_artifacts(tmp_dir, summary, results)

        assert os.path.exists(artifacts["benchmark_summary"])
        assert os.path.exists(artifacts["scenario_results"])
        assert os.path.exists(artifacts["benchmark_run"])
        assert os.path.exists(artifacts["benchmark_run_report"])

        with open(artifacts["benchmark_run_report"], "r", encoding="utf-8") as f:
            content = f.read()
            assert "Canonical Benchmark Run Report" in content
            assert "SMOKE_HAPPY_PATH" in content


# ==================== Test J: Failure Classification Works ====================

def test_j_failure_classification_works():
    """Requirement J: Verify that each expectation type produces the specified FailureClass on breach."""
    obs = ObservedStateSnapshot(
        merchant_id="merch_test",
        decision_mode="EXPLOIT",
        execution_authorized_9_1=True,  # Invariant violation!
        boundary_status="EXECUTION_REJECTED",
        reward_contribution_paise=-1000,
    )

    exp_safety = BenchmarkExpectation(
        expectation_id="exp_safety_viol",
        expectation_type=ExpectationType.INVARIANT,
        target_domain="decision",
        field_path="execution_authorized_9_1",
        operator="eq",
        expected_value=False,
        failure_class=FailureClass.SAFETY_FAILURE,
        description="Phase 9.1 must not authorize execution",
    )
    diag_safety = AssertionEvaluator.evaluate(exp_safety, obs)
    assert not diag_safety.passed
    assert diag_safety.failure_class == FailureClass.SAFETY_FAILURE

    exp_econ = BenchmarkExpectation(
        expectation_id="exp_econ_viol",
        expectation_type=ExpectationType.RELATIONAL,
        target_domain="outcome",
        field_path="reward_contribution_paise",
        operator="gte",
        expected_value=0,
        failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
        description="Reward cannot be negative",
    )
    diag_econ = AssertionEvaluator.evaluate(exp_econ, obs)
    assert not diag_econ.passed
    assert diag_econ.failure_class == FailureClass.ECONOMIC_INTEGRITY_FAILURE


# ==================== Test K: Expected Business Assertion Failure ====================

@pytest.mark.asyncio
async def test_k_expected_business_assertion_failure_reported(db_session):
    """Requirement K: Intentionally induce an assertion failure and confirm the harness marks FAIL with diagnostic."""
    failing_scenario = BenchmarkScenario(
        scenario_id="scen_induced_failure",
        description="Scenario with intentionally false expectation",
        category=ScenarioCategory.DECISION,
        merchant_id="merch_bench_smoke",
        buyer_context=BuyerContextInput(raw_prompt="travel pack under 5000 with 15.6 inch laptop sleeve"),
        initial_state=InitialStateSpec(
            merchant=InitialMerchantSpec(merchant_id="merch_bench_smoke", name="Smoke Merchant"),
            products=[
                InitialProductSpec(
                    product_id="prod_smoke_ind_01",
                    name="Smoke Pack",
                    sku="SKU-SMK-IND",
                    category="travel_backpack",
                    price_paise=450000,
                    cost_paise=250000,
                )
            ],
            active_policy_id="cand_smoke_base",
        ),
        execution_mode=BenchmarkExecutionMode.DECISION_ONLY,
        expected_invariants=[
            BenchmarkExpectation(
                expectation_id="impossible_expectation",
                expectation_type=ExpectationType.EXACT_VALUE,
                target_domain="decision",
                field_path="selected_strategy",
                operator="eq",
                expected_value="IMPOSSIBLE_NONEXISTENT_STRATEGY",
                failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
                description="This expectation is deliberately false to test harness failure reporting",
            )
        ],
    )
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, failing_scenario)
    assert result.status == BenchmarkStatus.FAIL
    assert result.assertions_failed == 1
    diag = next(d for d in result.diagnostics if not d.passed)
    assert diag.failure_class == FailureClass.EXPECTED_STATE_MISMATCH
    assert "IMPOSSIBLE_NONEXISTENT_STRATEGY" in diag.message


# ==================== Test L: Infrastructure Failure Reported as INCONCLUSIVE ====================

@pytest.mark.asyncio
async def test_l_infrastructure_failure_reported_as_inconclusive(db_session):
    """Requirement L: Verify unhandled infrastructure/setup errors result in INCONCLUSIVE (never falsely PASS)."""
    broken_scenario = BenchmarkScenario(
        scenario_id="scen_broken_setup",
        description="Scenario that induces infrastructure error (missing required buyer prompt)",
        category=ScenarioCategory.DECISION,
        merchant_id="merch_nonexistent_xyz",  # Merchant not in DB, setup omitted
        buyer_context=BuyerContextInput(raw_prompt="pack"),
        execution_mode=BenchmarkExecutionMode.DECISION_ONLY,
    )
    # The runtime will raise MerchantNotFoundError because merchant is not created
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, broken_scenario)
    assert result.status == BenchmarkStatus.INCONCLUSIVE
    assert any(d.failure_class == FailureClass.INFRASTRUCTURE_FAILURE for d in result.diagnostics)


# ==================== Test M: No Secret Leakage in Artifacts ====================

@pytest.mark.asyncio
async def test_m_no_secret_leakage_in_artifacts(db_session):
    """Requirement M: Verify secrets, private headers, credentials, and merchant unit economics are not leaked."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_SMOKE_HAPPY_PATH)
    res_dict = result.model_dump(mode="json")
    json_str = str(res_dict).lower()

    # Invariants on information hygiene
    assert "key_secret" not in json_str
    assert "cogs_paise" not in json_str
    assert "gross_margin_percent" not in json_str
    assert "bearer" not in json_str


# ==================== Test N: Merchant Scope is Preserved ====================

@pytest.mark.asyncio
async def test_n_merchant_scope_preserved(db_session):
    """Requirement N: Verify merchant_id is strictly preserved and auditable across scenario and result."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_SMOKE_HAPPY_PATH)
    assert result.merchant_id == "merch_bench_smoke"
    assert result.observed_state.merchant_id == "merch_bench_smoke"


# ==================== Test O: Scenario Execution and Assertion Counts Distinct ====================

@pytest.mark.asyncio
async def test_o_scenario_and_assertion_counts_distinct(db_session):
    """Requirement O: Ensure scenario execution counts and assertion evaluation counts are never conflated."""
    suite = [SCENARIO_SMOKE_HAPPY_PATH, SCENARIO_SMOKE_NO_OFFER]
    summary, results = await CanonicalBenchmarkRunner.run_suite(db_session, suite)

    assert summary.total_scenarios == 2
    # Multiple assertions per scenario
    assert summary.assertions_total >= 8
    assert summary.total_scenarios != summary.assertions_total


# ==================== Test P: Repeatability Comparison Works ====================

@pytest.mark.asyncio
async def test_p_repeatability_comparison_works(db_session):
    """Requirement P: Verify run_repeatability executes N times and asserts cross-run business consistency."""
    rep_result = await CanonicalBenchmarkRunner.run_repeatability(
        db_session,
        SCENARIO_SMOKE_HAPPY_PATH,
        repeat_count=3,
    )
    assert rep_result["repeat_count"] == 3
    assert rep_result["all_passed"] is True
    assert rep_result["is_reproducible"] is True
    assert len(rep_result["divergences"]) == 0


# ==================== Test Q: Runner Does Not Bypass Authoritative Services ====================

@pytest.mark.asyncio
async def test_q_runner_does_not_bypass_authoritative_services(db_session):
    """Requirement Q: Verify harness persists genuine records in CanonicalDecisionRecord, DecisionExecutionRecord, and OutcomeFeedbackRecord."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_SMOKE_HAPPY_PATH)
    assert result.status == BenchmarkStatus.PASS

    obs = result.observed_state
    # 1. CanonicalDecisionRecord
    dec = (await db_session.execute(select(CanonicalDecisionRecord).where(CanonicalDecisionRecord.id == obs.decision_id))).scalar_one()
    assert dec.opportunity_id == SCENARIO_SMOKE_HAPPY_PATH.scenario_id

    # 2. DecisionExecutionRecord
    dexec = (await db_session.execute(select(DecisionExecutionRecord).where(DecisionExecutionRecord.id == obs.execution_id))).scalar_one()
    assert dexec.decision_id == dec.id

    # 3. OutcomeFeedbackRecord
    out_rec = (await db_session.execute(select(OutcomeFeedbackRecord).where(OutcomeFeedbackRecord.id == obs.outcome_id))).scalar_one()
    assert out_rec.execution_id == dexec.id

    # 4. PolicyMemoryRecord
    mem_rec = (await db_session.execute(select(PolicyMemoryRecord).where(PolicyMemoryRecord.id == obs.memory_id))).scalar_one()
    assert mem_rec.merchant_id == SCENARIO_SMOKE_HAPPY_PATH.merchant_id
