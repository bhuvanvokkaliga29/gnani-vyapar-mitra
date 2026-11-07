"""Unit tests for Phase 5 ExecutionValidator."""

import pytest
from decimal import Decimal
from domain.intent_schemas import BuyerIntent, BudgetConstraint, ExclusionConstraint
from domain.commerce_schemas import RelationshipResponse
from services.policy.schemas import (
    PolicyProposal,
    PolicyCandidate,
    StrategyType,
    CandidateValidationStatus,
    IncentiveProposal
)
from services.execution.validator import ExecutionValidator
from services.execution.schemas import ExecutionRejectionReason
from tests.fixtures.commerce_fixtures import build_test_commerce_context


@pytest.fixture
def validator():
    return ExecutionValidator()


@pytest.fixture
def fresh_context():
    return build_test_commerce_context()


@pytest.fixture
def valid_proposal(fresh_context):
    p = fresh_context.products[0]
    candidate = PolicyCandidate(
        candidate_id="cand_test_01",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[p.id],
        bundle_components=[{"product_id": p.id, "quantity": 1}],
        rationale="Primary test pack",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    return PolicyProposal(
        proposal_id="prop_test_01",
        merchant_id=fresh_context.merchant_id,
        status="APPROVED_FOR_EVALUATION",
        candidates=[candidate],
        selected_candidate=candidate,
        total_candidates=1,
        valid_candidates_count=1
    )


def test_valid_candidate_execution_approved(validator, fresh_context, valid_proposal):
    """Valid proposal matching fresh database state is approved with exact paise."""
    candidate = valid_proposal.selected_candidate
    is_valid, reasons, econ, auth_amount = validator.revalidate_candidate(
        candidate=candidate,
        proposal=valid_proposal,
        fresh_context=fresh_context
    )
    assert is_valid is True
    assert reasons == []
    assert auth_amount == fresh_context.products[0].price_paise
    assert econ.is_compliant is True


def test_stale_inventory_out_of_stock_rejected(validator, fresh_context, valid_proposal):
    """If inventory was depleted between proposal generation and execution, reject with OUT_OF_STOCK."""
    candidate = valid_proposal.selected_candidate
    # Deplete stock in fresh context
    fresh_context.products[0].available_to_sell = 0

    is_valid, reasons, econ, auth_amount = validator.revalidate_candidate(
        candidate=candidate,
        proposal=valid_proposal,
        fresh_context=fresh_context
    )
    assert is_valid is False
    assert ExecutionRejectionReason.OUT_OF_STOCK in reasons
    assert auth_amount == 0


def test_stale_cost_margin_deterioration_rejected(validator, fresh_context, valid_proposal):
    """If product COGS increased, dropping margin below floor, reject with MARGIN_TOO_LOW."""
    candidate = valid_proposal.selected_candidate
    # Spike unit cost to 95% of price
    fresh_context.products[0].cost_paise = int(fresh_context.products[0].price_paise * 0.95)

    is_valid, reasons, econ, auth_amount = validator.revalidate_candidate(
        candidate=candidate,
        proposal=valid_proposal,
        fresh_context=fresh_context
    )
    assert is_valid is False
    assert ExecutionRejectionReason.MARGIN_TOO_LOW in reasons
    assert auth_amount == 0


def test_stale_product_deactivation_rejected(validator, fresh_context, valid_proposal):
    """If product was deactivated in fresh context, reject with PRODUCT_UNAVAILABLE."""
    candidate = valid_proposal.selected_candidate
    fresh_context.products[0].is_active = False

    is_valid, reasons, econ, auth_amount = validator.revalidate_candidate(
        candidate=candidate,
        proposal=valid_proposal,
        fresh_context=fresh_context
    )
    assert is_valid is False
    assert ExecutionRejectionReason.PRODUCT_UNAVAILABLE in reasons
    assert auth_amount == 0


def test_stale_relationship_bundle_rejected(validator, fresh_context):
    """If a complementary relationship was removed from fresh state, bundle is rejected."""
    p1 = fresh_context.products[0]
    p2 = fresh_context.products[1]
    candidate = PolicyCandidate(
        candidate_id="cand_bundle_01",
        strategy_type=StrategyType.COMPLEMENTARY_BUNDLE,
        product_ids=[p1.id, p2.id],
        bundle_components=[{"product_id": p1.id, "quantity": 1}, {"product_id": p2.id, "quantity": 1}],
        rationale="Bundle",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_bundle",
        merchant_id=fresh_context.merchant_id,
        status="APPROVED_FOR_EVALUATION",
        candidates=[candidate],
        selected_candidate=candidate,
        total_candidates=1,
        valid_candidates_count=1
    )

    # Empty out relationships in fresh context
    fresh_context.relationships = []

    is_valid, reasons, econ, auth_amount = validator.revalidate_candidate(
        candidate=candidate,
        proposal=proposal,
        fresh_context=fresh_context
    )
    assert is_valid is False
    assert ExecutionRejectionReason.RELATIONSHIP_INVALID in reasons


def test_no_offer_proposal_rejected(validator, fresh_context):
    """Proposals with NO_OFFER must be deterministically rejected from execution."""
    no_offer_cand = PolicyCandidate(
        candidate_id="cand_no_offer",
        strategy_type=StrategyType.NO_OFFER,
        product_ids=[],
        rationale="No offer possible",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_no_offer",
        merchant_id=fresh_context.merchant_id,
        status="VALID",
        candidates=[no_offer_cand],
        selected_candidate=no_offer_cand,
        total_candidates=1,
        valid_candidates_count=1
    )

    is_valid, reasons, econ, auth_amount = validator.revalidate_candidate(
        candidate=no_offer_cand,
        proposal=proposal,
        fresh_context=fresh_context
    )
    assert is_valid is False
    assert ExecutionRejectionReason.NO_EXECUTABLE_OFFER in reasons
    assert auth_amount == 0


def test_merchant_mismatch_rejected(validator, fresh_context, valid_proposal):
    """Proposal belonging to merchant A attempted against merchant B must be rejected."""
    valid_proposal.merchant_id = "merch_other_tenant"
    candidate = valid_proposal.selected_candidate

    is_valid, reasons, econ, auth_amount = validator.revalidate_candidate(
        candidate=candidate,
        proposal=valid_proposal,
        fresh_context=fresh_context
    )
    assert is_valid is False
    assert ExecutionRejectionReason.MERCHANT_MISMATCH in reasons
