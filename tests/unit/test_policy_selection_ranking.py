"""Unit tests for Phase 8.5 Deterministic Learned Policy Candidate Ranking & Selection.

Contract: policy-selection/v1
Verifies:
- Deterministic candidate ordering (predicted_contribution_paise DESC, tie-breakers).
- Mandatory NO_OFFER baseline injection and comparison.
- Invariance to input permutation.
- Uncertainty neutrality (UCB NEVER used for selection).
- Structural validation and candidate exclusion.
"""

import pytest
from decimal import Decimal
from domain.intent_schemas import BuyerIntent, BudgetConstraint, BudgetType
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    IncentiveProposal,
    CandidateValidationStatus,
    PolicyScore
)
from services.learning.algorithm import ContextualLinearUCB
from services.selection.ranking import (
    PolicyCandidateSelector,
    STRATEGY_PRIORITY,
    CANONICAL_BASELINE_POLICY_ID
)
from services.selection.errors import EmptyCandidateSetError, MalformedCandidateError


@pytest.fixture
def sample_intent():
    return BuyerIntent(
        category="backpack",
        budget=BudgetConstraint(budget_type=BudgetType.MAX, max_amount_paise=500000),
        quantity=1
    )


@pytest.fixture
def cold_start_model():
    return ContextualLinearUCB(merchant_id="m_unit_sel")


def make_cand(**kwargs) -> PolicyCandidate:
    """Helper to construct approved PolicyCandidate by default."""
    if "validation_status" not in kwargs:
        kwargs["validation_status"] = CandidateValidationStatus.APPROVED
    return PolicyCandidate(**kwargs)


def test_empty_candidates_raises_error(sample_intent, cold_start_model):
    """Empty candidate set must immediately raise EmptyCandidateSetError."""
    with pytest.raises(EmptyCandidateSetError):
        PolicyCandidateSelector.evaluate_and_rank_candidates(
            candidates=[],
            intent=sample_intent,
            buyer_context_key="bck_test",
            model=cold_start_model
        )


def test_missing_baseline_auto_injected(sample_intent, cold_start_model):
    """If candidates omit NO_OFFER, canonical baseline must be automatically injected."""
    c1 = make_cand(
        candidate_id="c_single",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["p1"],
        rationale="Single product"
    )
    selected, baseline, slate, reason = PolicyCandidateSelector.evaluate_and_rank_candidates(
        candidates=[c1],
        intent=sample_intent,
        buyer_context_key="bck_test",
        model=cold_start_model
    )
    assert any(c.is_baseline for c in slate)
    assert baseline.is_baseline is True
    assert baseline.policy_id == CANONICAL_BASELINE_POLICY_ID


def test_clear_highest_predicted_offer_selected(sample_intent):
    """Candidate with highest predicted contribution > baseline must be selected."""
    model = ContextualLinearUCB(merchant_id="m_trained")
    # Train model to favor bundle heavily
    x_bundle = [0.0] * 19
    x_bundle[0] = 1.0
    x_bundle[7] = 1.0  # is_comp_bundle
    for _ in range(10):
        model.update(x_bundle, 150000)

    c_bundle = make_cand(
        candidate_id="c_bundle",
        strategy_type=StrategyType.COMPLEMENTARY_BUNDLE,
        product_ids=["p1", "p2"],
        bundle_components=[{"product_id": "p1"}, {"product_id": "p2"}],
        rationale="High value bundle"
    )
    c_single = make_cand(
        candidate_id="c_single",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["p1"],
        rationale="Single product"
    )

    selected, baseline, slate, reason = PolicyCandidateSelector.evaluate_and_rank_candidates(
        candidates=[c_single, c_bundle],
        intent=sample_intent,
        buyer_context_key="bck_test",
        model=model
    )
    assert selected.policy_id == "c_bundle"
    assert selected.predicted_contribution_paise > baseline.predicted_contribution_paise
    assert reason == "HIGHEST_PREDICTED_CONTRIBUTION"
    assert slate[0].policy_id == "c_bundle"


def test_baseline_dominates_when_all_offers_negative(sample_intent):
    """When all offers predict negative contribution, NO_OFFER must be selected."""
    model = ContextualLinearUCB(merchant_id="m_neg")
    x = [0.0] * 19
    x[10] = 1.0  # is_bounded_discount
    # Update with strong negative reward
    for _ in range(10):
        model.update(x, -50000)

    c_disc = make_cand(
        candidate_id="c_disc",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=["p1"],
        incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("50.0")),
        rationale="Deep discount losing money"
    )

    selected, baseline, slate, reason = PolicyCandidateSelector.evaluate_and_rank_candidates(
        candidates=[c_disc],
        intent=sample_intent,
        buyer_context_key="bck_test",
        model=model
    )
    assert selected.is_baseline is True
    assert reason == "NO_OFFER_BASELINE_DOMINATES"
    assert selected.policy_id == CANONICAL_BASELINE_POLICY_ID


def test_baseline_selected_when_offers_tie_at_zero(sample_intent, cold_start_model):
    """In cold start where all offers tie at zero, NO_OFFER must be selected."""
    c1 = make_cand(
        candidate_id="c_single",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["p1"],
        rationale="Single product"
    )
    selected, baseline, slate, reason = PolicyCandidateSelector.evaluate_and_rank_candidates(
        candidates=[c1],
        intent=sample_intent,
        buyer_context_key="bck_test",
        model=cold_start_model
    )
    assert selected.is_baseline is True
    assert reason == "NO_VALID_POSITIVE_OFFER"


def test_deterministic_tie_breaking_order(sample_intent, cold_start_model):
    """When predictions tie, secondary tie-breaker order must be strictly deterministic:
    strategy_priority DESC -> policy_id ASC -> policy_version ASC.
    composite_score is NOT used in selection tie-breaking."""
    # 1. Strategy priority tie-break: Bundle (priority 7) beats Single Product (priority 5)
    c_bundle = make_cand(
        candidate_id="cand_b",
        strategy_type=StrategyType.COMPLEMENTARY_BUNDLE,
        product_ids=["p1", "p2"],
        bundle_components=[{"product_id": "p1"}, {"product_id": "p2"}],
        rationale="Bundle priority"
    )
    c_single = make_cand(
        candidate_id="cand_a",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["p1"],
        rationale="Single priority"
    )

    _, _, slate_strat, _ = PolicyCandidateSelector.evaluate_and_rank_candidates(
        candidates=[c_single, c_bundle],
        intent=sample_intent,
        buyer_context_key="bck_test",
        model=cold_start_model
    )
    rank_bnd = next(c.rank for c in slate_strat if c.policy_id == "cand_b")
    rank_sng = next(c.rank for c in slate_strat if c.policy_id == "cand_a")
    assert rank_bnd < rank_sng

    # 2. Same strategy priority: policy_id ASC lexicographical tie-break
    c_alpha = make_cand(
        candidate_id="cand_alpha",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["p1"],
        rationale="Alpha"
    )
    c_zeta = make_cand(
        candidate_id="cand_zeta",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["p1"],
        rationale="Zeta"
    )

    _, _, slate_lex, _ = PolicyCandidateSelector.evaluate_and_rank_candidates(
        candidates=[c_zeta, c_alpha],
        intent=sample_intent,
        buyer_context_key="bck_test",
        model=cold_start_model
    )
    rank_alpha = next(c.rank for c in slate_lex if c.policy_id == "cand_alpha")
    rank_zeta = next(c.rank for c in slate_lex if c.policy_id == "cand_zeta")
    assert rank_alpha < rank_zeta


def test_uncertainty_neutrality(sample_intent):
    """High uncertainty MUST NOT promote a candidate with lower predicted contribution.
    UCB score is never used for candidate selection!"""
    model = ContextualLinearUCB(merchant_id="m_ucb_neutral")
    # c_high is observed frequently, has higher expected contribution, but low uncertainty
    x_high = [0.0] * 19
    x_high[0] = 1.0
    x_high[6] = 1.0  # single product
    for _ in range(50):
        model.update(x_high, 50000)

    # c_novel has zero observations, zero prediction, but maximum uncertainty
    c_high = make_cand(
        candidate_id="c_high",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["p1"],
        rationale="Established product"
    )
    c_novel = make_cand(
        candidate_id="c_novel",
        strategy_type=StrategyType.VALUE_BUNDLE,
        product_ids=["p1", "p2"],
        bundle_components=[{"product_id": "p1"}, {"product_id": "p2"}],
        rationale="Unobserved bundle"
    )

    selected, baseline, slate, reason = PolicyCandidateSelector.evaluate_and_rank_candidates(
        candidates=[c_novel, c_high],
        intent=sample_intent,
        buyer_context_key="bck_test",
        model=model
    )
    # Even though c_novel has higher uncertainty and potentially higher UCB,
    # c_high has higher predicted contribution, so c_high MUST be selected!
    assert selected.policy_id == "c_high"
    # Find slate scores
    score_novel = next(c for c in slate if c.policy_id == "c_novel")
    score_high = next(c for c in slate if c.policy_id == "c_high")
    assert score_novel.uncertainty > score_high.uncertainty
    assert score_high.predicted_contribution_paise > score_novel.predicted_contribution_paise
    assert score_high.rank < score_novel.rank


def test_candidate_input_order_invariance(sample_intent):
    """Permuting the order of the candidates list must not change ranking or selection."""
    model = ContextualLinearUCB(merchant_id="m_perm")
    x = [0.0] * 19
    x[0] = 1.0
    x[6] = 1.0
    model.update(x, 25000)

    c1 = make_cand(candidate_id="c1", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=["p1"], rationale="1")
    c2 = make_cand(candidate_id="c2", strategy_type=StrategyType.BOUNDED_DISCOUNT, product_ids=["p1"], rationale="2")
    c3 = make_cand(candidate_id="c3", strategy_type=StrategyType.NO_OFFER, product_ids=[], rationale="3")

    res1_sel, _, res1_slate, _ = PolicyCandidateSelector.evaluate_and_rank_candidates([c1, c2, c3], sample_intent, "k", model)
    res2_sel, _, res2_slate, _ = PolicyCandidateSelector.evaluate_and_rank_candidates([c3, c1, c2], sample_intent, "k", model)
    res3_sel, _, res3_slate, _ = PolicyCandidateSelector.evaluate_and_rank_candidates([c2, c3, c1], sample_intent, "k", model)

    assert res1_sel.policy_id == res2_sel.policy_id == res3_sel.policy_id
    assert [c.policy_id for c in res1_slate] == [c.policy_id for c in res2_slate] == [c.policy_id for c in res3_slate]


def test_structurally_invalid_candidate_excluded(sample_intent, cold_start_model):
    """A candidate marked REJECTED by Phase 4 validation must be marked ineligible."""
    c_rej = PolicyCandidate(
        candidate_id="c_bad",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["p1"],
        validation_status=CandidateValidationStatus.REJECTED,
        rationale="Price below margin floor"
    )
    c_ok = PolicyCandidate(
        candidate_id="c_ok",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["p1"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Valid candidate"
    )

    selected, baseline, slate, reason = PolicyCandidateSelector.evaluate_and_rank_candidates(
        candidates=[c_rej, c_ok],
        intent=sample_intent,
        buyer_context_key="bck_test",
        model=cold_start_model
    )
    score_rej = next(c for c in slate if c.policy_id == "c_bad")
    assert score_rej.selection_eligible is False
    assert score_rej.exclusion_reason == "VALIDATION_REJECTED"
    assert selected.policy_id != "c_bad"
