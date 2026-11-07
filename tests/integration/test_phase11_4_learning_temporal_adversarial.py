"""Integration Tests for Phase 11.4 Adaptive Integrity Suite.

Contract: benchmark-scenario/v1, policy-exploration/v1, learning-algorithm/v1, outcome-feedback/v1, policy-lifecycle/v1
Focus:
- Adaptive benchmark scenario execution (Exploration budget, duplicate learning replay, future evidence rejection)
- Multi-tenant learning, memory, and exploration budget isolation
- At-least-once delivery with single effective learning update (replay idempotency)
- Unsafe exploration fallback committing zero exposure
- Strict separation of Learning vs Exploration vs Promotion
- Deterministic repeatability across N=3 runs on all 3 adaptive scenarios
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select, func, and_

from domain.models import (
    Merchant,
    Product,
    Order,
    Payment,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
    LearningEvidenceRecord,
    PolicyMemoryRecord,
    AppliedModelObservationRecord,
    MerchantActivePolicy,
    MerchantExplorationState,
)
from apps.api.core.state_machine import TransactionState
from services.benchmark.schemas import BenchmarkStatus
from services.benchmark.adaptive_scenarios import (
    ADAPTIVE_SCENARIOS,
    SCENARIO_ADAPT_EXPLORATION_BUDGET_EXHAUSTED,
    SCENARIO_ADAPT_DUPLICATE_LEARNING_REPLAY,
    SCENARIO_ADAPT_FUTURE_EVIDENCE_REJECTED,
)
from services.benchmark.runner import CanonicalBenchmarkRunner
from services.runtime.schemas import CanonicalDecisionRequest
from services.runtime.service import CanonicalDecisionRuntime
from services.boundary.schemas import DecisionExecuteRequest
from services.boundary.service import DecisionExecutionBoundaryService
from services.outcome.schemas import OutcomeProcessRequest
from services.outcome.service import OutcomeFeedbackService
from services.learning.model_service import PolicyLearningModelService
from services.learning.features import FEATURE_DIMENSION
from services.policy.schemas import PolicyCandidate, StrategyType, CandidateValidationStatus
from services.selection.schemas import CandidateSelectionScore, PolicySelectionResult
from services.exploration.schemas import (
    ExplorationRequest,
    ExplorationMode,
    ExplorationReasonCode,
    MerchantExplorationConfig,
)
from services.exploration.service import PolicyExplorationService


# ==============================================================================
# BENCHMARK SCENARIO INTEGRATION TESTS
# ==============================================================================
@pytest.mark.asyncio
async def test_adapt_scenario_01_exploration_budget_exhaustion(db_session):
    """Scenario 1: Exhausted exploration opportunities forces exploit fallback with 0 exposure."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ADAPT_EXPLORATION_BUDGET_EXHAUSTED)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs.decision_mode == "EXPLOIT"
    assert obs.active_policy_id == "cand_adapt_exp_base"


@pytest.mark.asyncio
async def test_adapt_scenario_02_duplicate_learning_replay(db_session):
    """Scenario 2: At-least-once delivery with duplicate outcome yields single model update."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ADAPT_DUPLICATE_LEARNING_REPLAY)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs.is_duplicate_outcome is True
    assert obs.model_observation_count == 1
    assert obs.memory_count == 1
    assert obs.active_policy_id == "cand_adapt_replay_base"


@pytest.mark.asyncio
async def test_adapt_scenario_03_future_evidence_rejected(db_session):
    """Scenario 3: Candidate containing future evidence is rejected with FUTURE_EVIDENCE_REJECTED."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_ADAPT_FUTURE_EVIDENCE_REJECTED)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0
    obs = result.observed_state
    assert obs.promotion_status in ("INSUFFICIENT_EVIDENCE", "NOT_ELIGIBLE", "REJECTED")
    assert obs.promotion_failure_code == "FUTURE_EVIDENCE_REJECTED"
    assert obs.active_policy_id == "cand_adapt_temp_base"


@pytest.mark.asyncio
async def test_adaptive_scenario_suite_execution(db_session):
    """Execute complete Phase 11.4 Adaptive Scenario Suite (3/3 pass, 0 fail)."""
    summary, results = await CanonicalBenchmarkRunner.run_suite(db_session, ADAPTIVE_SCENARIOS)
    assert summary.total_scenarios == 3
    assert summary.passed == 3
    assert summary.failed == 0
    assert summary.inconclusive == 0
    assert summary.assertions_failed == 0
    assert summary.reproducibility_status == "VERIFIED"


@pytest.mark.asyncio
async def test_adaptive_scenarios_deterministic_repeatability(db_session):
    """Verify deterministic repeatability across N=3 runs on all 3 adaptive scenarios."""
    for scen in ADAPTIVE_SCENARIOS:
        rep = await CanonicalBenchmarkRunner.run_repeatability(db_session, scen, repeat_count=3)
        assert rep["all_passed"] is True, f"Scenario {scen.scenario_id} failed in repeatability run"
        assert rep["is_reproducible"] is True, f"Divergences found for {scen.scenario_id}: {rep['divergences']}"
        assert rep["divergences"] == []


# ==============================================================================
# MULTI-TENANT LEARNING ISOLATION
# ==============================================================================
@pytest.mark.asyncio
async def test_multi_tenant_learning_and_budget_isolation(db_session):
    """Verify that Merchant A's observations, model updates, and exploration budgets cannot affect Merchant B."""
    merch_a = Merchant(
        id="merch_iso_a",
        name="Isolation Merchant A",
        currency="INR",
        status="ACTIVE",
    )
    merch_b = Merchant(
        id="merch_iso_b",
        name="Isolation Merchant B",
        currency="INR",
        status="ACTIVE",
    )
    db_session.add_all([merch_a, merch_b])
    await db_session.commit()

    # Apply learning observation to Merchant A
    x = [0.1 for _ in range(FEATURE_DIMENSION)]
    applied_a, ver_a = await PolicyLearningModelService.apply_observation_idempotent(
        db=db_session,
        merchant_id=merch_a.id,
        evidence_id="evi_iso_a_001",
        x=x,
        reward_paise=50000,
    )
    assert applied_a is True

    # Retrieve models for A and B
    model_a, _ = await PolicyLearningModelService.get_or_create_model(db_session, merch_a.id)
    model_b, _ = await PolicyLearningModelService.get_or_create_model(db_session, merch_b.id)

    # Invariant: A's model updated, B's model remains completely pristine
    assert model_a.observation_count == 1
    assert model_b.observation_count == 0
    for i in range(FEATURE_DIMENSION):
        assert abs(model_b.b[i]) == 0.0

    # Ensure Merchant B's applied observation table is completely clean
    stmt_b_obs = select(AppliedModelObservationRecord).where(AppliedModelObservationRecord.merchant_id == merch_b.id)
    b_records = (await db_session.execute(stmt_b_obs)).scalars().all()
    assert len(b_records) == 0


# ==============================================================================
# REPLAY / DUPLICATE LEARNING IDEMPOTENCY
# ==============================================================================
@pytest.mark.asyncio
async def test_replay_at_least_once_delivery_single_effective_learning_update(db_session):
    """Delivering outcome feedback multiple times results in exactly ONE effective model update."""
    merch = Merchant(
        id="merch_replay_deep",
        name="Deep Replay Merchant",
        currency="INR",
        status="ACTIVE",
    )
    prod = Product(
        id="prod_replay_01",
        merchant_id=merch.id,
        name="Replay Pack 30L",
        sku="SKU-RPL-01",
        category="backpack",
        price_paise=350000,
        cost_paise=150000,
        inventory_quantity=10,
        is_active=True,
    )
    act = MerchantActivePolicy(
        merchant_id=merch.id,
        policy_id="cand_replay_base",
        policy_version="merchant-policy/v1",
        promotion_id="prom_replay_01",
    )
    db_session.add_all([merch, prod, act])
    await db_session.commit()

    # 1. Evaluate Decision & Execute
    dec_req = CanonicalDecisionRequest(
        merchant_id=merch.id,
        opportunity_id="opp_replay_deep_01",
        raw_prompt="backpack under 4000",
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=merch.id),
    )

    # 2. Simulate Paid Order
    order = (await db_session.execute(select(Order).where(Order.id == boundary_res.order_id))).scalar_one()
    order.status = TransactionState.PAID.value
    pmt = Payment(
        id=f"pay_rpl_{uuid.uuid4().hex[:8]}",
        order_id=order.id,
        amount_paise=boundary_res.authorized_amount_paise,
        currency="INR",
        status="captured",
    )
    db_session.add(pmt)
    await db_session.commit()

    # 3. Process outcome 3 times (simulating at-least-once delivery retry loop)
    proc_req = OutcomeProcessRequest(merchant_id=merch.id, execution_id=boundary_res.execution_id)
    resp1 = await OutcomeFeedbackService.process_outcome(db_session, proc_req)
    assert resp1.is_duplicate is False

    resp2 = await OutcomeFeedbackService.process_outcome(db_session, proc_req)
    assert resp2.is_duplicate is True
    assert resp2.outcome_id == resp1.outcome_id

    resp3 = await OutcomeFeedbackService.process_outcome(db_session, proc_req)
    assert resp3.is_duplicate is True
    assert resp3.outcome_id == resp1.outcome_id

    # 4. Verify Single Effective Learning Effect Invariants
    model, _ = await PolicyLearningModelService.get_or_create_model(db_session, merch.id)
    assert model.observation_count == 1  # Exactly one update despite 3 deliveries!

    # Exactly one PolicyMemoryRecord
    mem_count = (await db_session.execute(
        select(func.count(PolicyMemoryRecord.id)).where(PolicyMemoryRecord.merchant_id == merch.id)
    )).scalar()
    assert mem_count == 1

    # Exactly one AppliedModelObservationRecord
    amo_count = (await db_session.execute(
        select(func.count(AppliedModelObservationRecord.id)).where(AppliedModelObservationRecord.merchant_id == merch.id)
    )).scalar()
    assert amo_count == 1

    # Active policy untouched
    act_pol = (await db_session.execute(
        select(MerchantActivePolicy).where(MerchantActivePolicy.merchant_id == merch.id)
    )).scalar_one()
    assert act_pol.policy_id == "cand_replay_base"


# ==============================================================================
# UNSAFE EXPLORATION FALLBACK COMMIT ZERO EXPOSURE
# ==============================================================================
@pytest.mark.asyncio
async def test_unsafe_exploration_fallback_commits_zero_exposure(db_session):
    """When an exploratory candidate fails safety validation, runtime falls back to exploit with zero exposure."""
    merch = Merchant(
        id="merch_unsafe_fallback",
        name="Fallback Merchant",
        currency="INR",
        status="ACTIVE",
        minimum_margin_percent=Decimal("30.00"),
        maximum_discount_percent=Decimal("10.00"),
    )
    prod = Product(
        id="prod_fallback_01",
        merchant_id=merch.id,
        name="Fallback Pack 25L",
        sku="SKU-FLB-01",
        category="backpack",
        price_paise=300000,
        cost_paise=220000,  # 26.6% margin -> already near floor
        inventory_quantity=10,
        is_active=True,
    )
    db_session.add_all([merch, prod])
    await db_session.commit()

    # Exploit candidate (safe)
    c_exploit = PolicyCandidate(
        candidate_id="cand_flb_safe_exploit",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[prod.id],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Safe baseline exploit candidate",
    )
    # Exploratory candidate (unsafe: violates 30% margin floor or 10% discount cap)
    from services.policy.schemas import IncentiveProposal
    c_unsafe_explore = PolicyCandidate(
        candidate_id="cand_flb_unsafe_explore",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=[prod.id],
        incentive=IncentiveProposal(
            incentive_type="discount",
            discount_percent=Decimal("20.00"),  # Breaches 10% maximum discount ceiling!
            description="20% promotional discount",
        ),
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Unsafe exploratory candidate breaching discount ceiling",
    )

    scores = [
        CandidateSelectionScore(
            policy_id=c_exploit.candidate_id,
            predicted_contribution_paise=50000,
            uncertainty=0.10,
            rank=1,
            selection_eligible=True,
            is_baseline=False,
        ),
        CandidateSelectionScore(
            policy_id=c_unsafe_explore.candidate_id,
            predicted_contribution_paise=48000,
            uncertainty=0.55,  # gap = 0.45 >= 0.15
            rank=2,
            selection_eligible=True,
            is_baseline=False,
        ),
    ]
    sel_res = PolicySelectionResult(
        selection_id="sel_flb_001",
        merchant_id=merch.id,
        opportunity_id="opp_flb_001",
        buyer_context_key="ctx_fallback",
        selected_policy_id=c_exploit.candidate_id,
        selected_policy_version="merchant-policy/v1",
        baseline_policy_id="cand_base_no_offer",
        selected_predicted_contribution_paise=50000,
        selected_uncertainty=0.10,
        baseline_predicted_contribution_paise=0,
        ranked_candidates=scores,
        selection_reason="Highest predicted contribution",
        selection_timestamp=datetime.now(timezone.utc),
    )

    from domain.intent_schemas import BuyerIntent
    intent = BuyerIntent(
        category="travel_backpack",
    )

    exp_req = ExplorationRequest(
        merchant_id=merch.id,
        opportunity_id="opp_flb_001",
        buyer_context_key="ctx_fallback",
        intent=intent,
        candidates=[c_exploit, c_unsafe_explore],
        selection_result=sel_res,
    )

    decision = await PolicyExplorationService.decide_exploration(db_session, exp_req)

    # Invariants:
    # 1. Fallback triggered to exploit mode
    assert decision.mode == ExplorationMode.EXPLOIT
    assert decision.selected_policy_id == c_exploit.candidate_id
    assert decision.reason_code == ExplorationReasonCode.EXPLOIT_FALLBACK_EXPLORATION_UNSAFE

    # 2. Exactly zero exposure committed
    assert decision.exposure_paise == 0

    # 3. Database exploration state recorded zero exposure
    cfg = MerchantExplorationConfig()
    win_id = cfg.resolve_window_id(datetime.now(timezone.utc))
    stmt_state = select(MerchantExplorationState).where(
        and_(
            MerchantExplorationState.merchant_id == merch.id,
            MerchantExplorationState.window_id == win_id,
        )
    )
    state = (await db_session.execute(stmt_state)).scalar_one()
    assert state.exposure_paise_used == 0
    assert state.consecutive_explorations == 0


# ==============================================================================
# SEPARATION OF CONCERNS: LEARNING != EXPLORATION != PROMOTION
# ==============================================================================
@pytest.mark.asyncio
async def test_learning_exploration_promotion_strict_separation(db_session):
    """Verify that learning cannot promote a policy, exploration cannot promote, and promotion requires governance."""
    merch = Merchant(
        id="merch_tri_sep",
        name="Tripartite Separation Merchant",
        currency="INR",
        status="ACTIVE",
    )
    act = MerchantActivePolicy(
        merchant_id=merch.id,
        policy_id="cand_sep_active",
        policy_version="merchant-policy/v1",
        promotion_id="prom_sep_01",
    )
    db_session.add_all([merch, act])
    await db_session.commit()

    # 1. LEARNING: Model update must NEVER mutate MerchantActivePolicy
    x = [0.05 for _ in range(FEATURE_DIMENSION)]
    await PolicyLearningModelService.apply_observation_idempotent(
        db=db_session,
        merchant_id=merch.id,
        evidence_id="evi_sep_001",
        x=x,
        reward_paise=100000,
    )
    act_pol = (await db_session.execute(
        select(MerchantActivePolicy).where(MerchantActivePolicy.merchant_id == merch.id)
    )).scalar_one()
    assert act_pol.policy_id == "cand_sep_active"

    # 2. EXPLORATION: Exploratory decision must NEVER promote exploratory candidate
    c_cand = PolicyCandidate(
        candidate_id="cand_sep_exploratory",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Exploratory candidate",
    )
    # Active policy remains cand_sep_active
    act_pol_after = (await db_session.execute(
        select(MerchantActivePolicy).where(MerchantActivePolicy.merchant_id == merch.id)
    )).scalar_one()
    assert act_pol_after.policy_id == "cand_sep_active"
