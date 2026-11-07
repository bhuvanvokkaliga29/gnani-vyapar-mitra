"""Unit tests for transparent PolicyScorer and multi-factor ranking."""

import pytest
from decimal import Decimal
from domain.intent_schemas import BuyerIntent, BudgetConstraint, AttributePreference
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    CandidateValidationStatus,
    CandidateEconomics
)
from services.policy.ranking import PolicyScorer
from tests.fixtures.commerce_fixtures import build_test_commerce_context


@pytest.fixture
def scorer():
    return PolicyScorer()


def test_rejected_candidate_receives_zero_score(scorer):
    """Rejected candidates must receive 0.0 for composite score."""
    context = build_test_commerce_context()
    intent = BuyerIntent(category="travel_backpack")
    cand = PolicyCandidate(
        candidate_id="cand_rej",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        rationale="Rejected candidate",
        validation_status=CandidateValidationStatus.REJECTED
    )
    scored = scorer.score_candidate(cand, intent, context)
    assert scored.score.composite_score == 0.0


def test_approved_candidate_scoring(scorer):
    """Approved candidate receives positive, transparent score."""
    context = build_test_commerce_context()
    intent = BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(max_amount_paise=500000),
        preferences=[AttributePreference(attribute="weight", preference="lightweight")]
    )
    cand = PolicyCandidate(
        candidate_id="cand_appr",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        rationale="Approved candidate",
        validation_status=CandidateValidationStatus.APPROVED,
        deterministic_economics=CandidateEconomics(
            gross_revenue_paise=499900,
            net_revenue_paise=499900,
            total_cogs_paise=250000,
            gross_profit_paise=249900,
            gross_margin_percent=Decimal("49.99"),
            is_compliant=True
        )
    )
    scored = scorer.score_candidate(cand, intent, context)
    assert scored.score is not None
    assert scored.score.composite_score > 0.50
    assert scored.score.buyer_fit_score > 0.60  # +0.10 for lightweight preference match


def test_ranking_approved_before_rejected(scorer):
    """Approved candidates must always precede rejected candidates in ranking."""
    context = build_test_commerce_context()
    cand_appr = PolicyCandidate(
        candidate_id="cand_appr",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        rationale="Good",
        validation_status=CandidateValidationStatus.APPROVED
    )
    cand_rej = PolicyCandidate(
        candidate_id="cand_rej",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_daypack_01"],
        rationale="Bad",
        validation_status=CandidateValidationStatus.REJECTED
    )
    intent = BuyerIntent(category="travel_backpack")
    cand_appr = scorer.score_candidate(cand_appr, intent, context)
    cand_rej = scorer.score_candidate(cand_rej, intent, context)

    # Pass in rejected first
    ranked = scorer.rank_candidates([cand_rej, cand_appr], context)
    assert ranked[0].candidate_id == "cand_appr"
    assert ranked[1].candidate_id == "cand_rej"


def test_objective_increase_aov_favors_bundle(scorer):
    """Under INCREASE_AOV, a valid complementary bundle scores higher alignment than a single item."""
    context = build_test_commerce_context(business_objective="INCREASE_AOV")
    intent = BuyerIntent(category="travel_backpack")

    cand_single = PolicyCandidate(
        candidate_id="cand_single",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        rationale="Single item",
        validation_status=CandidateValidationStatus.APPROVED,
        deterministic_economics=CandidateEconomics(
            gross_revenue_paise=499900,
            net_revenue_paise=499900,
            total_cogs_paise=250000,
            gross_profit_paise=249900,
            gross_margin_percent=Decimal("49.99"),
            is_compliant=True
        )
    )

    cand_bundle = PolicyCandidate(
        candidate_id="cand_bundle",
        strategy_type=StrategyType.COMPLEMENTARY_BUNDLE,
        product_ids=["prod_backpack_01", "prod_sleeve_01"],
        rationale="Bundle",
        validation_status=CandidateValidationStatus.APPROVED,
        deterministic_economics=CandidateEconomics(
            gross_revenue_paise=599800,
            net_revenue_paise=599800,
            total_cogs_paise=290000,
            gross_profit_paise=309800,
            gross_margin_percent=Decimal("51.65"),
            is_compliant=True
        )
    )

    s1 = scorer.score_candidate(cand_single, intent, context)
    s2 = scorer.score_candidate(cand_bundle, intent, context)

    assert s2.score.objective_alignment_score >= s1.score.objective_alignment_score
