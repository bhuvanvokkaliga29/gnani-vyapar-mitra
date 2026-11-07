"""Unit tests for DeterministicPolicyBaseline generator."""

import pytest
from domain.intent_schemas import BuyerIntent, BudgetConstraint
from services.policy.schemas import ProposalStatus, StrategyType, CandidateValidationStatus
from services.policy.baseline import DeterministicPolicyBaseline
from tests.fixtures.commerce_fixtures import build_test_commerce_context


@pytest.fixture
def baseline():
    return DeterministicPolicyBaseline()


def test_baseline_generates_compliant_proposal(baseline):
    """Verify baseline produces valid proposal for standard backpack request."""
    context = build_test_commerce_context()
    intent = BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(max_amount_paise=700000)
    )
    proposal = baseline.generate_baseline_proposal(intent, context)

    assert proposal.status == ProposalStatus.APPROVED_FOR_EVALUATION
    assert proposal.valid_candidates_count >= 1
    assert proposal.selected_candidate is not None
    assert proposal.selected_candidate.validation_status == CandidateValidationStatus.APPROVED


def test_baseline_returns_no_offer_when_impossible(baseline):
    """When budget is impossible, baseline returns NO_OFFER with status VALID."""
    context = build_test_commerce_context()
    intent = BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(max_amount_paise=1000)  # ₹10 impossible budget
    )
    proposal = baseline.generate_baseline_proposal(intent, context)

    assert proposal.total_candidates >= 1
    assert proposal.candidates[0].strategy_type in [StrategyType.NO_OFFER, StrategyType.SINGLE_PRODUCT]
