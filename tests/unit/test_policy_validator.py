"""Unit tests for deterministic PolicyValidator and commercial guardrails."""

import pytest
from decimal import Decimal
from domain.intent_schemas import (
    BuyerIntent,
    BudgetConstraint,
    BudgetType,
    AttributeRequirement,
    ExclusionConstraint,
    ConfidenceLevel,
    OperatorType
)
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    CandidateValidationStatus,
    RejectionReason,
    IncentiveProposal
)
from services.policy.validator import PolicyValidator
from tests.fixtures.commerce_fixtures import build_test_commerce_context


@pytest.fixture
def context():
    return build_test_commerce_context()


@pytest.fixture
def validator():
    return PolicyValidator()


def test_valid_single_product_approved(validator, context):
    """Valid product within budget and margin floor should be APPROVED."""
    intent = BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(max_amount_paise=500000)
    )
    candidate = PolicyCandidate(
        candidate_id="cand_1",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        rationale="Valid test candidate",
        confidence=ConfidenceLevel.HIGH
    )
    result = validator.validate_candidate(candidate, intent, context)
    assert result.validation_status == CandidateValidationStatus.APPROVED
    assert len(result.rejection_reasons) == 0
    assert result.deterministic_economics is not None
    assert result.deterministic_economics.gross_revenue_paise == 499900


def test_over_budget_rejected(validator, context):
    """Product exceeding buyer MAX budget must be REJECTED with OVER_BUDGET."""
    intent = BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(max_amount_paise=400000)  # Backpack is ₹4,999 > ₹4,000
    )
    candidate = PolicyCandidate(
        candidate_id="cand_1",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        rationale="Over budget test",
        confidence=ConfidenceLevel.HIGH
    )
    result = validator.validate_candidate(candidate, intent, context)
    assert result.validation_status == CandidateValidationStatus.REJECTED
    assert RejectionReason.OVER_BUDGET.value in result.rejection_reasons


def test_margin_floor_violation_rejected(validator, context):
    """Product or bundle below merchant margin floor must be REJECTED with MARGIN_TOO_LOW."""
    intent = BuyerIntent(category="travel_backpack")
    # prod_low_margin_backpack has 10% margin, floor is 25%
    candidate = PolicyCandidate(
        candidate_id="cand_1",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_low_margin_backpack"],
        rationale="Low margin test",
        confidence=ConfidenceLevel.HIGH
    )
    result = validator.validate_candidate(candidate, intent, context)
    assert result.validation_status == CandidateValidationStatus.REJECTED
    assert RejectionReason.MARGIN_TOO_LOW.value in result.rejection_reasons


def test_discount_ceiling_violation_rejected(validator, context):
    """Proposed discount exceeding discount ceiling (8.00%) must be REJECTED."""
    intent = BuyerIntent(category="travel_backpack")
    candidate = PolicyCandidate(
        candidate_id="cand_1",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=["prod_backpack_01"],
        incentive=IncentiveProposal(
            incentive_type="discount",
            discount_percent=Decimal("15.00")  # Ceiling is 8.00%
        ),
        rationale="Excessive discount test",
        confidence=ConfidenceLevel.HIGH
    )
    result = validator.validate_candidate(candidate, intent, context)
    assert result.validation_status == CandidateValidationStatus.REJECTED
    assert RejectionReason.DISCOUNT_TOO_HIGH.value in result.rejection_reasons


def test_out_of_stock_rejected(validator, context):
    """Item with 0 available stock must be REJECTED with OUT_OF_STOCK."""
    intent = BuyerIntent(category="laptop_sleeve")
    candidate = PolicyCandidate(
        candidate_id="cand_1",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_out_of_stock_sleeve"],
        rationale="OOS test",
        confidence=ConfidenceLevel.HIGH
    )
    result = validator.validate_candidate(candidate, intent, context)
    assert result.validation_status == CandidateValidationStatus.REJECTED
    assert RejectionReason.OUT_OF_STOCK.value in result.rejection_reasons


def test_buyer_exclusion_violation_rejected(validator, context):
    """Product containing excluded material (e.g. leather) must be REJECTED."""
    intent = BuyerIntent(
        category="travel_backpack",
        exclusions=[ExclusionConstraint(attribute="material", excluded_value="leather")]
    )
    candidate = PolicyCandidate(
        candidate_id="cand_1",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_leather_backpack_01"],
        rationale="Exclusion test",
        confidence=ConfidenceLevel.HIGH
    )
    result = validator.validate_candidate(candidate, intent, context)
    assert result.validation_status == CandidateValidationStatus.REJECTED
    assert RejectionReason.EXCLUDED_BY_BUYER.value in result.rejection_reasons


def test_buyer_hard_requirement_violation_rejected(validator, context):
    """Product failing hard requirement (16-inch laptop size required, 14-inch sleeve offered) must be REJECTED."""
    intent = BuyerIntent(
        category="laptop_sleeve",
        requirements=[AttributeRequirement(attribute="laptop_size", operator=OperatorType.GTE, value=16.0, unit="inch")]
    )
    candidate = PolicyCandidate(
        candidate_id="cand_1",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_sleeve_14_inch"],
        rationale="Size mismatch test",
        confidence=ConfidenceLevel.HIGH
    )
    result = validator.validate_candidate(candidate, intent, context)
    assert result.validation_status == CandidateValidationStatus.REJECTED
    assert RejectionReason.REQUIREMENT_NOT_MET.value in result.rejection_reasons


def test_unknown_sku_rejected(validator, context):
    """Nonexistent product SKU must be REJECTED with UNKNOWN_PRODUCT."""
    intent = BuyerIntent(category="travel_backpack")
    candidate = PolicyCandidate(
        candidate_id="cand_1",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["nonexistent_sku_12345"],
        rationale="Unknown SKU test",
        confidence=ConfidenceLevel.HIGH
    )
    result = validator.validate_candidate(candidate, intent, context)
    assert result.validation_status == CandidateValidationStatus.REJECTED
    assert RejectionReason.UNKNOWN_PRODUCT.value in result.rejection_reasons


def test_invalid_bundle_relationship_rejected(validator, context):
    """Bundle containing products without an explicit relationship must be REJECTED."""
    intent = BuyerIntent(category="travel_backpack")
    # prod_leather_backpack_01 and prod_mouse_01 have NO relationship in context
    candidate = PolicyCandidate(
        candidate_id="cand_1",
        strategy_type=StrategyType.COMPLEMENTARY_BUNDLE,
        product_ids=["prod_leather_backpack_01", "prod_mouse_01"],
        rationale="Invalid bundle test",
        confidence=ConfidenceLevel.HIGH
    )
    result = validator.validate_candidate(candidate, intent, context)
    assert result.validation_status == CandidateValidationStatus.REJECTED
    assert RejectionReason.INVALID_RELATIONSHIP.value in result.rejection_reasons
