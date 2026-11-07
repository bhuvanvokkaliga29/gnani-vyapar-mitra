"""Unit tests for Policy Agent schemas, contracts, and enums."""

import pytest
from decimal import Decimal
from pydantic import ValidationError
from domain.intent_schemas import ConfidenceLevel
from services.policy.schemas import (
    PolicyProposal,
    PolicyCandidate,
    StrategyType,
    ProposalStatus,
    CandidateValidationStatus,
    RejectionReason,
    PolicyScore,
    CandidateEconomics,
    IncentiveProposal
)


def test_strategy_type_enums():
    """Verify expected strategy taxonomy values."""
    assert StrategyType.SINGLE_PRODUCT.value == "SINGLE_PRODUCT"
    assert StrategyType.COMPLEMENTARY_BUNDLE.value == "COMPLEMENTARY_BUNDLE"
    assert StrategyType.VALUE_BUNDLE.value == "VALUE_BUNDLE"
    assert StrategyType.ALTERNATIVE_PRODUCT.value == "ALTERNATIVE_PRODUCT"
    assert StrategyType.NON_PRICE_INCENTIVE.value == "NON_PRICE_INCENTIVE"
    assert StrategyType.BOUNDED_DISCOUNT.value == "BOUNDED_DISCOUNT"
    assert StrategyType.NO_OFFER.value == "NO_OFFER"


def test_extra_fields_forbidden_on_candidate():
    """Extra unexpected fields must be rejected by Pydantic."""
    with pytest.raises(ValidationError):
        PolicyCandidate(
            candidate_id="cand_1",
            strategy_type=StrategyType.SINGLE_PRODUCT,
            product_ids=["p1"],
            rationale="Test",
            confidence=ConfidenceLevel.HIGH,
            unauthorized_field="malicious_payload"  # forbidden
        )


def test_extra_fields_forbidden_on_proposal():
    """Extra unexpected fields must be rejected on PolicyProposal."""
    with pytest.raises(ValidationError):
        PolicyProposal(
            proposal_id="prop_1",
            merchant_id="merch_1",
            status=ProposalStatus.VALID,
            candidates=[],
            unauthorized_field="malicious_payload"  # forbidden
        )


def test_candidate_economics_schema():
    """Verify CandidateEconomics model integrity."""
    econ = CandidateEconomics(
        gross_revenue_paise=500000,
        promotional_discount_paise=25000,
        net_revenue_paise=475000,
        total_cogs_paise=250000,
        gross_profit_paise=225000,
        gross_margin_percent=Decimal("47.37"),
        effective_discount_percent=Decimal("5.00"),
        is_compliant=True
    )
    assert econ.net_revenue_paise == 475000
    assert econ.gross_margin_percent == Decimal("47.37")
    assert econ.is_compliant is True


def test_policy_score_bounds():
    """Scores must be bounded between 0.0 and 1.0."""
    score = PolicyScore(
        buyer_fit_score=0.85,
        economic_value_score=0.75,
        objective_alignment_score=0.80,
        constraint_safety_score=0.90,
        composite_score=0.82
    )
    assert 0.0 <= score.composite_score <= 1.0

    with pytest.raises(ValidationError):
        PolicyScore(
            buyer_fit_score=1.5,  # Exceeds 1.0
            economic_value_score=0.5,
            objective_alignment_score=0.5,
            constraint_safety_score=0.5,
            composite_score=0.5
        )
