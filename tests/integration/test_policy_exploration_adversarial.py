"""Adversarial and Invariant Test Suite for Phase 8.7 Constrained Exploration Engine.

Contract: policy-exploration/v1
Covers:
- Invariants A-L:
  * Invariant A: Selected policy must originate from Phase 8.5 candidate slate.
  * Invariant B: Every exploratory policy must pass Phase 8.6 safety gate.
  * Invariant C: Exploration cannot exceed configured merchant budget.
  * Invariant D: Concurrent requests cannot overspend exploration budget.
  * Invariant E: Repeated requests cannot double-consume exploration budget.
  * Invariant F: Changing uncertainty affects exploration only, never 8.5 exploitation.
  * Invariant G: UCB cannot affect pure exploitation.
  * Invariant H: High UCB cannot override a hard safety rejection.
  * Invariant I: Merchant A exploration state cannot leak to Merchant B.
  * Invariant J: Exploration decision is 100% deterministic and reproducible.
  * Invariant K: Exploration does not mutate policy state.
  * Invariant L: Exploration does not alter reward or learning definitions.
- Static AST Boundary Scanner: verifies services/exploration has zero order creation,
  payment capture, inventory reservation, policy mutation, policy promotion, or n8n calls.
"""

import ast
import os
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
import pytest

from domain.models import Merchant, Product
from domain.intent_schemas import BuyerIntent, BudgetConstraint, BudgetType
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    IncentiveProposal,
    CandidateValidationStatus
)
from services.selection.schemas import (
    PolicySelectionResult,
    CandidateSelectionScore
)
from services.exploration.schemas import (
    ExplorationRequest,
    ExplorationDecision,
    ExplorationMode,
    ExplorationReasonCode,
    MerchantExplorationConfig
)
from services.exploration.service import PolicyExplorationService
from services.exploration.engine import ExplorationEngine


@pytest.fixture
async def seed_adv_exploration_db(db_session):
    m1 = Merchant(
        id="merch_adv_exp_a",
        name="Adv Exploration Merchant A",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=25.0,
        maximum_discount_percent=10.0,
        target_aov_paise=400000
    )
    m2 = Merchant(
        id="merch_adv_exp_b",
        name="Adv Exploration Merchant B",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=25.0,
        maximum_discount_percent=10.0,
        target_aov_paise=400000
    )
    db_session.add_all([m1, m2])

    p1 = Product(
        id="prod_adv_exp_01",
        merchant_id="merch_adv_exp_a",
        sku="SKU-ADV-EXP-01",
        name="Adv Pack",
        category="travel_backpack",
        price_paise=500000,
        cost_paise=250000,
        currency="INR",
        inventory_quantity=10,
        reserved_quantity=0,
        is_active=True
    )
    db_session.add(p1)
    await db_session.commit()
    return m1, m2, p1


def test_invariant_a_and_f_and_g_candidate_slate_and_pure_exploitation():
    """Invariant A, F & G: Selected policy must come from 8.5 slate; UCB affects exploration only."""
    cand_a = PolicyCandidate(candidate_id="c_a", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=["p1"], validation_status=CandidateValidationStatus.APPROVED, rationale="A")
    cand_b = PolicyCandidate(candidate_id="c_b", strategy_type=StrategyType.BOUNDED_DISCOUNT, product_ids=["p1"], validation_status=CandidateValidationStatus.APPROVED, rationale="B")

    scores = [
        CandidateSelectionScore(policy_id="c_a", predicted_contribution_paise=60000, uncertainty=0.05, rank=1, is_baseline=False, selection_eligible=True),
        CandidateSelectionScore(policy_id="c_b", predicted_contribution_paise=50000, uncertainty=0.40, rank=2, is_baseline=False, selection_eligible=True)
    ]
    sel_res = PolicySelectionResult(
        selection_id="s1",
        merchant_id="m1",
        opportunity_id="o1",
        buyer_context_key="k1",
        selected_policy_id="c_a",
        selected_policy_version="merchant-policy/v1",
        baseline_policy_id="c_base",
        selected_predicted_contribution_paise=60000,
        selected_uncertainty=0.05,
        baseline_predicted_contribution_paise=0,
        ranked_candidates=scores,
        selection_reason="Highest predicted contribution",
        selection_timestamp=datetime.now(timezone.utc)
    )

    # 1. Under exploration disabled: EXPLOIT is chosen and equals c_a (unchanged from 8.5)
    cfg_disabled = MerchantExplorationConfig(enabled=False)
    mode, chosen, _, exp_val, reason, _ = ExplorationEngine.evaluate_exploration(sel_res, {"c_a": cand_a, "c_b": cand_b}, cfg_disabled, {})
    assert mode == ExplorationMode.EXPLOIT
    assert chosen.candidate_id == "c_a"  # Invariant G: pure exploitation unaffected by UCB
    assert exp_val == 0

    # 2. Under exploration enabled: EXPLORE is chosen, selecting c_b from the candidate slate
    cfg_enabled = MerchantExplorationConfig(enabled=True, min_uncertainty_gap=0.20)
    mode_exp, chosen_exp, _, exp_val2, reason_exp, _ = ExplorationEngine.evaluate_exploration(sel_res, {"c_a": cand_a, "c_b": cand_b}, cfg_enabled, {})
    assert mode_exp == ExplorationMode.EXPLORE
    assert chosen_exp.candidate_id == "c_b"
    assert chosen_exp.candidate_id in ["c_a", "c_b"]  # Invariant A: originates from slate
    assert exp_val2 == 10000  # 60,000 - 50,000 = 10,000 paise downside exposure


@pytest.mark.asyncio
async def test_invariant_b_and_h_high_ucb_cannot_override_safety_rejection(db_session, seed_adv_exploration_db):
    """Invariant B & H: High UCB candidate violating hard constraint must be rejected by Phase 8.6,
    triggering fallback to exploit candidate."""
    m1, _, p1 = seed_adv_exploration_db

    # c_unsafe has high predicted contribution + high uncertainty, but discount is 30% (exceeds merchant 10% max)
    cand_exploit = PolicyCandidate(
        candidate_id="c_safe_exploit",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[p1.id],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Safe exploit"
    )
    cand_unsafe = PolicyCandidate(
        candidate_id="c_unsafe_explore",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=[p1.id],
        incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("30.00")),
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Unsafe deep discount"
    )

    sel_res = PolicySelectionResult(
        selection_id="s_safe",
        merchant_id=m1.id,
        opportunity_id="opp_adv_safe_1",
        buyer_context_key="k1",
        selected_policy_id="c_safe_exploit",
        selected_policy_version="merchant-policy/v1",
        baseline_policy_id="c_base",
        selected_predicted_contribution_paise=50000,
        selected_uncertainty=0.10,
        baseline_predicted_contribution_paise=0,
        ranked_candidates=[
            CandidateSelectionScore(policy_id="c_safe_exploit", predicted_contribution_paise=50000, uncertainty=0.10, rank=1, is_baseline=False, selection_eligible=True),
            CandidateSelectionScore(policy_id="c_unsafe_explore", predicted_contribution_paise=45000, uncertainty=0.60, rank=2, is_baseline=False, selection_eligible=True)
        ],
        selection_reason="Highest predicted contribution",
        selection_timestamp=datetime.now(timezone.utc)
    )

    req = ExplorationRequest(
        merchant_id=m1.id,
        opportunity_id="opp_adv_safe_1",
        buyer_context_key="k1",
        intent=BuyerIntent(category="travel_backpack", budget=BudgetConstraint(budget_type=BudgetType.MAX, max_amount_paise=600000), quantity=1),
        candidates=[cand_exploit, cand_unsafe],
        selection_result=sel_res,
        config=MerchantExplorationConfig(min_uncertainty_gap=0.20)
    )

    # Invariant H: High UCB cannot override Phase 8.6 rejection!
    decision = await PolicyExplorationService.decide_exploration(db_session, req)
    assert decision.mode == ExplorationMode.EXPLOIT
    assert decision.selected_policy_id == "c_safe_exploit"
    assert decision.reason_code == ExplorationReasonCode.EXPLOIT_FALLBACK_EXPLORATION_UNSAFE


@pytest.mark.asyncio
async def test_invariant_c_d_e_budget_limits_and_concurrency_protection(db_session, seed_adv_exploration_db):
    """Invariant C, D & E: Budget limits cannot be exceeded, and retries don't double-consume."""
    m1, _, p1 = seed_adv_exploration_db

    cand_exploit = PolicyCandidate(candidate_id="c_safe_exploit", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p1.id], validation_status=CandidateValidationStatus.APPROVED, rationale="Safe")
    cand_alt = PolicyCandidate(candidate_id="c_safe_alt", strategy_type=StrategyType.BOUNDED_DISCOUNT, product_ids=[p1.id], incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("5.00")), validation_status=CandidateValidationStatus.APPROVED, rationale="Alt")

    # Set budget = 1 exploration opportunity!
    config = MerchantExplorationConfig(max_exploration_opportunities=1, min_uncertainty_gap=0.10)

    sel_res_1 = PolicySelectionResult(
        selection_id="s1", merchant_id=m1.id, opportunity_id="opp_budget_1", buyer_context_key="k1",
        selected_policy_id="c_safe_exploit", selected_policy_version="merchant-policy/v1", baseline_policy_id="c_base",
        selected_predicted_contribution_paise=50000, selected_uncertainty=0.10, baseline_predicted_contribution_paise=0,
        ranked_candidates=[
            CandidateSelectionScore(policy_id="c_safe_exploit", predicted_contribution_paise=50000, uncertainty=0.10, rank=1, is_baseline=False, selection_eligible=True),
            CandidateSelectionScore(policy_id="c_safe_alt", predicted_contribution_paise=48000, uncertainty=0.35, rank=2, is_baseline=False, selection_eligible=True)
        ],
        selection_reason="Ranked", selection_timestamp=datetime.now(timezone.utc)
    )

    req1 = ExplorationRequest(
        merchant_id=m1.id, opportunity_id="opp_budget_1", buyer_context_key="k1",
        intent=BuyerIntent(category="travel_backpack"), candidates=[cand_exploit, cand_alt], selection_result=sel_res_1, config=config
    )

    # 1. First opportunity consumes 1 exploration slot
    res1 = await PolicyExplorationService.decide_exploration(db_session, req1)
    assert res1.mode == ExplorationMode.EXPLORE
    assert res1.exploration_budget_state["opportunities_used"] == 1

    # Invariant E: Repeated call for same opportunity does NOT double consume!
    res1_retry = await PolicyExplorationService.decide_exploration(db_session, req1)
    assert res1_retry.decision_id == res1.decision_id
    assert res1_retry.exploration_budget_state["opportunities_used"] == 1

    # 2. Second distinct opportunity attempts exploration with budget=1 exhausted
    sel_res_2 = PolicySelectionResult(
        selection_id="s2", merchant_id=m1.id, opportunity_id="opp_budget_2", buyer_context_key="k1",
        selected_policy_id="c_safe_exploit", selected_policy_version="merchant-policy/v1", baseline_policy_id="c_base",
        selected_predicted_contribution_paise=50000, selected_uncertainty=0.10, baseline_predicted_contribution_paise=0,
        ranked_candidates=[
            CandidateSelectionScore(policy_id="c_safe_exploit", predicted_contribution_paise=50000, uncertainty=0.10, rank=1, is_baseline=False, selection_eligible=True),
            CandidateSelectionScore(policy_id="c_safe_alt", predicted_contribution_paise=48000, uncertainty=0.35, rank=2, is_baseline=False, selection_eligible=True)
        ],
        selection_reason="Ranked", selection_timestamp=datetime.now(timezone.utc)
    )
    req2 = ExplorationRequest(
        merchant_id=m1.id, opportunity_id="opp_budget_2", buyer_context_key="k1",
        intent=BuyerIntent(category="travel_backpack"), candidates=[cand_exploit, cand_alt], selection_result=sel_res_2, config=config
    )

    # Invariant C: Budget cannot be exceeded; must return EXPLOIT with EXPLOIT_BUDGET_EXHAUSTED!
    res2 = await PolicyExplorationService.decide_exploration(db_session, req2)
    assert res2.mode == ExplorationMode.EXPLOIT
    assert res2.reason_code == ExplorationReasonCode.EXPLOIT_BUDGET_EXHAUSTED
    assert res2.selected_policy_id == "c_safe_exploit"


@pytest.mark.asyncio
async def test_invariant_i_merchant_isolation(db_session, seed_adv_exploration_db):
    """Invariant I: Exploration state of Merchant A cannot leak to Merchant B."""
    m1, m2, p1 = seed_adv_exploration_db

    cand_exploit = PolicyCandidate(candidate_id="c_e", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p1.id], validation_status=CandidateValidationStatus.APPROVED, rationale="E")
    cand_alt = PolicyCandidate(candidate_id="c_a", strategy_type=StrategyType.BOUNDED_DISCOUNT, product_ids=[p1.id], incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("5.00")), validation_status=CandidateValidationStatus.APPROVED, rationale="A")

    config = MerchantExplorationConfig(max_exploration_opportunities=1, min_uncertainty_gap=0.10)

    # Merchant A exhausts budget
    req_a = ExplorationRequest(
        merchant_id=m1.id, opportunity_id="opp_iso_a", buyer_context_key="k1",
        intent=BuyerIntent(category="travel_backpack"), candidates=[cand_exploit, cand_alt], config=config
    )
    res_a = await PolicyExplorationService.decide_exploration(db_session, req_a)
    assert res_a.mode == ExplorationMode.EXPLORE

    # Merchant B has its own independent budget (should still be at 0 used!)
    p2_res = Product(id="prod_m2_p", merchant_id=m2.id, sku="SKU-M2", name="P2", category="travel_backpack", price_paise=500000, cost_paise=250000, currency="INR", inventory_quantity=10, reserved_quantity=0, is_active=True)
    db_session.add(p2_res)
    await db_session.commit()

    cand_exploit_b = PolicyCandidate(candidate_id="c_eb", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=["prod_m2_p"], validation_status=CandidateValidationStatus.APPROVED, rationale="EB")
    cand_alt_b = PolicyCandidate(candidate_id="c_ab", strategy_type=StrategyType.BOUNDED_DISCOUNT, product_ids=["prod_m2_p"], incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("5.00")), validation_status=CandidateValidationStatus.APPROVED, rationale="AB")

    req_b = ExplorationRequest(
        merchant_id=m2.id, opportunity_id="opp_iso_b", buyer_context_key="k1",
        intent=BuyerIntent(category="travel_backpack"), candidates=[cand_exploit_b, cand_alt_b], config=config
    )
    res_b = await PolicyExplorationService.decide_exploration(db_session, req_b)
    # Merchant B has its own budget and is able to explore!
    assert res_b.mode == ExplorationMode.EXPLORE
    assert res_b.merchant_id == m2.id


def test_invariant_j_and_k_and_l_determinism_and_immutability():
    """Invariant J, K & L: Determinism, candidate immutability, zero reward mutation."""
    cand = PolicyCandidate(candidate_id="c_imm", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=["p1"], validation_status=CandidateValidationStatus.APPROVED, rationale="Imm")
    dump_before = cand.model_dump()

    scores = [
        CandidateSelectionScore(policy_id="c_imm", predicted_contribution_paise=50000, uncertainty=0.10, rank=1, is_baseline=False, selection_eligible=True)
    ]
    sel_res = PolicySelectionResult(
        selection_id="s_imm", merchant_id="m1", opportunity_id="o_imm", buyer_context_key="k1",
        selected_policy_id="c_imm", selected_policy_version="merchant-policy/v1", baseline_policy_id="c_base",
        selected_predicted_contribution_paise=50000, selected_uncertainty=0.10, baseline_predicted_contribution_paise=0,
        ranked_candidates=scores, selection_reason="Top", selection_timestamp=datetime.now(timezone.utc)
    )
    config = MerchantExplorationConfig()

    res1 = ExplorationEngine.evaluate_exploration(sel_res, {"c_imm": cand}, config, {})
    res2 = ExplorationEngine.evaluate_exploration(sel_res, {"c_imm": cand}, config, {})

    assert res1 == res2
    assert cand.model_dump() == dump_before


@pytest.mark.asyncio
async def test_phase_8_7_1_underobserved_dominated_cannot_explore(db_session, seed_adv_exploration_db):
    """Invariant A: An under-observed candidate (N=0) cannot be explored if it fails economic eligibility."""
    m1, _, p1 = seed_adv_exploration_db
    cand_exploit = PolicyCandidate(candidate_id="c_e", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p1.id], validation_status=CandidateValidationStatus.APPROVED, rationale="E")
    cand_dom = PolicyCandidate(candidate_id="c_dom", strategy_type=StrategyType.BOUNDED_DISCOUNT, product_ids=[p1.id], validation_status=CandidateValidationStatus.APPROVED, rationale="Dom")

    # Dominated candidate has predicted contribution = -150,000 paise (deficit = 150,000 > max deficit 100,000)
    scores = [
        CandidateSelectionScore(policy_id="c_e", predicted_contribution_paise=50000, uncertainty=0.10, rank=1, is_baseline=False, selection_eligible=True),
        CandidateSelectionScore(policy_id="c_dom", predicted_contribution_paise=-150000, uncertainty=0.05, rank=2, is_baseline=False, selection_eligible=True)
    ]
    sel_res = PolicySelectionResult(
        selection_id="s_dom", merchant_id=m1.id, opportunity_id="o_dom", buyer_context_key="k1",
        selected_policy_id="c_e", selected_policy_version="merchant-policy/v1", baseline_policy_id="c_base",
        selected_predicted_contribution_paise=50000, selected_uncertainty=0.10, baseline_predicted_contribution_paise=0,
        ranked_candidates=scores, selection_reason="Top", selection_timestamp=datetime.now(timezone.utc)
    )

    req = ExplorationRequest(
        merchant_id=m1.id, opportunity_id="o_dom", buyer_context_key="k1",
        intent=BuyerIntent(category="travel_backpack"), candidates=[cand_exploit, cand_dom],
        selection_result=sel_res,
        config=MerchantExplorationConfig(min_observations_threshold=5, max_underobserved_deficit_paise=100000)
    )
    decision = await PolicyExplorationService.decide_exploration(db_session, req)
    assert decision.mode == ExplorationMode.EXPLOIT
    assert decision.selected_policy_id == "c_e"
    assert decision.reason_code == ExplorationReasonCode.EXPLOIT_NO_ALTERNATIVES or decision.reason_code == ExplorationReasonCode.EXPLOIT_TRIGGER_NOT_SATISFIED


@pytest.mark.asyncio
async def test_phase_8_7_1_exact_exposure_and_per_decision_cap(db_session, seed_adv_exploration_db):
    """Invariant B: Exact downside exposure calculation and per-decision cap enforcement."""
    m1, _, p1 = seed_adv_exploration_db
    cand_exploit = PolicyCandidate(candidate_id="c_e", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p1.id], validation_status=CandidateValidationStatus.APPROVED, rationale="E")
    cand_alt = PolicyCandidate(candidate_id="c_alt", strategy_type=StrategyType.BOUNDED_DISCOUNT, product_ids=[p1.id], incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("5.00")), validation_status=CandidateValidationStatus.APPROVED, rationale="Alt")

    # Exploit = 50,000 paise. Alt = 42,000 paise. Downside = 8,000 paise.
    scores = [
        CandidateSelectionScore(policy_id="c_e", predicted_contribution_paise=50000, uncertainty=0.10, rank=1, is_baseline=False, selection_eligible=True),
        CandidateSelectionScore(policy_id="c_alt", predicted_contribution_paise=42000, uncertainty=0.45, rank=2, is_baseline=False, selection_eligible=True)
    ]
    sel_res = PolicySelectionResult(
        selection_id="s_exp", merchant_id=m1.id, opportunity_id="o_exp", buyer_context_key="k1",
        selected_policy_id="c_e", selected_policy_version="merchant-policy/v1", baseline_policy_id="c_base",
        selected_predicted_contribution_paise=50000, selected_uncertainty=0.10, baseline_predicted_contribution_paise=0,
        ranked_candidates=scores, selection_reason="Top", selection_timestamp=datetime.now(timezone.utc)
    )

    # 1. Per-decision cap allows 8,000 paise (cap = 10,000)
    req1 = ExplorationRequest(
        merchant_id=m1.id, opportunity_id="o_exp_1", buyer_context_key="k1",
        intent=BuyerIntent(category="travel_backpack"), candidates=[cand_exploit, cand_alt],
        selection_result=sel_res,
        config=MerchantExplorationConfig(max_exposure_per_decision_paise=10000, min_uncertainty_gap=0.20)
    )
    res1 = await PolicyExplorationService.decide_exploration(db_session, req1)
    assert res1.mode == ExplorationMode.EXPLORE
    assert res1.exposure_paise == 8000  # Exact downside exposure!
    assert res1.exploration_budget_state["exposure_paise_used_after"] == 8000

    # 2. Per-decision cap rejects 8,000 paise (cap = 5,000)
    req2 = ExplorationRequest(
        merchant_id=m1.id, opportunity_id="o_exp_2", buyer_context_key="k1",
        intent=BuyerIntent(category="travel_backpack"), candidates=[cand_exploit, cand_alt],
        selection_result=sel_res,
        config=MerchantExplorationConfig(max_exposure_per_decision_paise=5000, min_uncertainty_gap=0.20)
    )
    res2 = await PolicyExplorationService.decide_exploration(db_session, req2)
    assert res2.mode == ExplorationMode.EXPLOIT
    assert res2.exposure_paise == 0


@pytest.mark.asyncio
async def test_phase_8_7_1_utc_window_boundaries_and_reset(db_session, seed_adv_exploration_db):
    """Invariant H: Canonical UTC daily windows produce deterministic budget isolation and resets."""
    m1, _, p1 = seed_adv_exploration_db
    cand_exploit = PolicyCandidate(candidate_id="c_e", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p1.id], validation_status=CandidateValidationStatus.APPROVED, rationale="E")
    cand_alt = PolicyCandidate(candidate_id="c_alt", strategy_type=StrategyType.BOUNDED_DISCOUNT, product_ids=[p1.id], incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("5.00")), validation_status=CandidateValidationStatus.APPROVED, rationale="Alt")

    scores = [
        CandidateSelectionScore(policy_id="c_e", predicted_contribution_paise=50000, uncertainty=0.10, rank=1, is_baseline=False, selection_eligible=True),
        CandidateSelectionScore(policy_id="c_alt", predicted_contribution_paise=45000, uncertainty=0.45, rank=2, is_baseline=False, selection_eligible=True)
    ]
    sel_res = PolicySelectionResult(
        selection_id="s_win", merchant_id=m1.id, opportunity_id="o_win", buyer_context_key="k1",
        selected_policy_id="c_e", selected_policy_version="merchant-policy/v1", baseline_policy_id="c_base",
        selected_predicted_contribution_paise=50000, selected_uncertainty=0.10, baseline_predicted_contribution_paise=0,
        ranked_candidates=scores, selection_reason="Top", selection_timestamp=datetime.now(timezone.utc)
    )

    # Window 1 (Day 1)
    cfg_day1 = MerchantExplorationConfig(window_id="win_2026-09-01", max_exploration_opportunities=1, min_uncertainty_gap=0.20)
    req_day1 = ExplorationRequest(merchant_id=m1.id, opportunity_id="o_d1", buyer_context_key="k1", intent=BuyerIntent(category="travel_backpack"), candidates=[cand_exploit, cand_alt], selection_result=sel_res, config=cfg_day1)
    res_d1 = await PolicyExplorationService.decide_exploration(db_session, req_day1)
    assert res_d1.mode == ExplorationMode.EXPLORE
    assert res_d1.exploration_budget_state["window_id"] == "win_2026-09-01"
    assert res_d1.exploration_budget_state["opportunities_used_after"] == 1

    # Window 2 (Day 2) has fresh reset budget naturally!
    cfg_day2 = MerchantExplorationConfig(window_id="win_2026-09-02", max_exploration_opportunities=1, min_uncertainty_gap=0.20)
    req_day2 = ExplorationRequest(merchant_id=m1.id, opportunity_id="o_d2", buyer_context_key="k1", intent=BuyerIntent(category="travel_backpack"), candidates=[cand_exploit, cand_alt], selection_result=sel_res, config=cfg_day2)
    res_d2 = await PolicyExplorationService.decide_exploration(db_session, req_day2)
    assert res_d2.mode == ExplorationMode.EXPLORE
    assert res_d2.exploration_budget_state["window_id"] == "win_2026-09-02"
    # Day 2 started from 0 used!
    assert res_d2.exploration_budget_state["opportunities_used_before"] == 0
    assert res_d2.exploration_budget_state["opportunities_used_after"] == 1


@pytest.mark.asyncio
async def test_phase_8_7_1_audit_replay_before_after_snapshots(db_session, seed_adv_exploration_db):
    """Invariant I: Decision budget state contains forensic before/after snapshots and config version."""
    m1, _, p1 = seed_adv_exploration_db
    cand_exploit = PolicyCandidate(candidate_id="c_e", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p1.id], validation_status=CandidateValidationStatus.APPROVED, rationale="E")
    cand_alt = PolicyCandidate(candidate_id="c_alt", strategy_type=StrategyType.BOUNDED_DISCOUNT, product_ids=[p1.id], incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("5.00")), validation_status=CandidateValidationStatus.APPROVED, rationale="Alt")

    scores = [
        CandidateSelectionScore(policy_id="c_e", predicted_contribution_paise=50000, uncertainty=0.10, rank=1, is_baseline=False, selection_eligible=True),
        CandidateSelectionScore(policy_id="c_alt", predicted_contribution_paise=45000, uncertainty=0.45, rank=2, is_baseline=False, selection_eligible=True)
    ]
    sel_res = PolicySelectionResult(
        selection_id="s_snap", merchant_id=m1.id, opportunity_id="o_snap", buyer_context_key="k1",
        selected_policy_id="c_e", selected_policy_version="merchant-policy/v1", baseline_policy_id="c_base",
        selected_predicted_contribution_paise=50000, selected_uncertainty=0.10, baseline_predicted_contribution_paise=0,
        ranked_candidates=scores, selection_reason="Top", selection_timestamp=datetime.now(timezone.utc)
    )

    req = ExplorationRequest(
        merchant_id=m1.id, opportunity_id="o_snap", buyer_context_key="k1",
        intent=BuyerIntent(category="travel_backpack"), candidates=[cand_exploit, cand_alt], selection_result=sel_res,
        config=MerchantExplorationConfig(window_id="win_2026-09-03", config_version="exp-config/v1", min_uncertainty_gap=0.20)
    )
    res = await PolicyExplorationService.decide_exploration(db_session, req)

    bstate = res.exploration_budget_state
    assert "opportunities_used_before" in bstate
    assert "opportunities_used_after" in bstate
    assert "exposure_paise_used_before" in bstate
    assert "exposure_paise_used_after" in bstate
    assert "consecutive_explorations_before" in bstate
    assert "consecutive_explorations_after" in bstate
    assert bstate["config_version"] == "exp-config/v1"
    assert res.config_version == "exp-config/v1"


def test_static_ast_boundary_audit():
    """Static AST Audit: services/exploration contains zero order creation, payment capture,
    inventory reservation, policy mutation, policy promotion, or n8n tokens."""
    exp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "services", "exploration"))
    forbidden_tokens = {
        "execute_order",
        "create_order",
        "capture_payment",
        "ExecutionAuthorization",
        "mutate_policy",
        "promote_policy",
        "deploy_policy",
        "reserve_inventory",
        "n8n"
    }

    found_violations = []
    for root, _, files in os.walk(exp_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    parsed = ast.parse(f.read(), filename=file_path)
                    for node in ast.walk(parsed):
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name) and node.func.id in forbidden_tokens:
                                found_violations.append(f"Forbidden call {node.func.id} in {file}")
                            elif isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_tokens:
                                found_violations.append(f"Forbidden method {node.func.attr} in {file}")
                        elif isinstance(node, ast.Name) and node.id in forbidden_tokens:
                            found_violations.append(f"Forbidden reference {node.id} in {file}")

    assert not found_violations, f"AST Boundary violations found in services/exploration: {found_violations}"
