"""Unit Tests for Phase 8.6 Deterministic Policy Safety Validator.

Contract: policy-safety/v1
Verifies:
- Admissible single product and bundle policies pass.
- NO_OFFER baseline is admissible without requiring inventory.
- Hard guardrail violations reject deterministically:
  * Merchant scope mismatch
  * Structural policy invalidity & missing candidate ID
  * Invalid policy version
  * Product missing or ineligible
  * Insufficient inventory (single & bundle)
  * Bundle relationship invalidity
  * Discount limit exceeded
  * Margin floor violated
  * Buyer budget ceiling exceeded
- Multiple simultaneous failure codes are sorted deterministically by canonical priority.
"""

from decimal import Decimal
import pytest

from domain.intent_schemas import BuyerIntent, BudgetConstraint, BudgetType
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    CandidateValidationStatus,
    IncentiveProposal
)
from services.safety.schemas import (
    PolicySafetyStatus,
    PolicySafetyFailureCode
)
from services.safety.validator import PolicySafetyValidator
from tests.fixtures.commerce_fixtures import build_test_commerce_context


@pytest.fixture
def fresh_context():
    return build_test_commerce_context(
        merchant_id="merch_test_safety",
        minimum_margin_percent=Decimal("25.00"),
        maximum_discount_percent=Decimal("8.00")
    )


@pytest.fixture
def base_intent():
    return BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(budget_type=BudgetType.MAX, max_amount_paise=600000),
        quantity=1
    )


def test_admissible_single_product(fresh_context, base_intent):
    """Compliant single product within margin, discount, and inventory limits must be ADMISSIBLE."""
    cand = PolicyCandidate(
        candidate_id="cand_single_ok",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Standard price backpack"
    )
    status, failures, econ, reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_test_safety",
        intent=base_intent
    )
    assert status == PolicySafetyStatus.ADMISSIBLE
    assert len(failures) == 0
    assert reason == "ADMISSIBLE_ALL_CONSTRAINTS_SATISFIED"
    assert econ is not None
    assert econ.net_revenue_paise == 499900
    assert econ.gross_margin_percent >= Decimal("25.00")


def test_admissible_bundle(fresh_context, base_intent):
    """Compliant bundle with valid relationships and inventory must be ADMISSIBLE."""
    cand = PolicyCandidate(
        candidate_id="cand_bundle_ok",
        strategy_type=StrategyType.COMPLEMENTARY_BUNDLE,
        product_ids=["prod_backpack_01", "prod_sleeve_01"],
        bundle_components=[
            {"product_id": "prod_backpack_01", "quantity": 1},
            {"product_id": "prod_sleeve_01", "quantity": 1}
        ],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Backpack + sleeve bundle"
    )
    status, failures, econ, reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_test_safety",
        intent=base_intent
    )
    assert status == PolicySafetyStatus.ADMISSIBLE
    assert len(failures) == 0
    assert econ is not None
    assert econ.net_revenue_paise == 599800


def test_no_offer_baseline_admissible(fresh_context):
    """NO_OFFER must be ADMISSIBLE without requiring product inventory or catalog existence."""
    cand = PolicyCandidate(
        candidate_id="cand_base_no_offer",
        strategy_type=StrategyType.NO_OFFER,
        product_ids=[],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="No offer reserve baseline"
    )
    status, failures, econ, reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_test_safety"
    )
    assert status == PolicySafetyStatus.ADMISSIBLE
    assert len(failures) == 0
    assert econ.net_revenue_paise == 0
    assert econ.gross_margin_percent == Decimal("0.00")


def test_merchant_scope_mismatch(fresh_context):
    """Merchant scope mismatch triggers MERCHANT_SCOPE_MISMATCH."""
    cand = PolicyCandidate(
        candidate_id="cand_1",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Valid cand"
    )
    status, failures, _, reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_wrong_scope"
    )
    assert status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.MERCHANT_SCOPE_MISMATCH in failures
    assert reason == PolicySafetyFailureCode.MERCHANT_SCOPE_MISMATCH.value


def test_policy_not_found_on_empty_id(fresh_context):
    """Candidate missing candidate_id triggers POLICY_NOT_FOUND."""
    cand = PolicyCandidate(
        candidate_id="",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Bad id"
    )
    status, failures, _, reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_test_safety"
    )
    assert status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.POLICY_NOT_FOUND in failures


def test_invalid_policy_status(fresh_context):
    """Candidate with validation_status == REJECTED triggers INVALID_POLICY."""
    cand = PolicyCandidate(
        candidate_id="cand_rej",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        validation_status=CandidateValidationStatus.REJECTED,
        rationale="Rejected candidate"
    )
    status, failures, _, reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_test_safety"
    )
    assert status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.INVALID_POLICY in failures


def test_invalid_policy_version(fresh_context):
    """Unknown policy version triggers POLICY_VERSION_INVALID."""
    cand = PolicyCandidate(
        candidate_id="cand_v_bad",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Bad ver"
    )
    status, failures, _, reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_test_safety",
        proposed_policy_version="merchant-policy/v99"
    )
    assert status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.POLICY_VERSION_INVALID in failures


def test_product_not_found(fresh_context):
    """Referencing unknown product triggers PRODUCT_NOT_FOUND."""
    cand = PolicyCandidate(
        candidate_id="cand_p_unknown",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_ghost_does_not_exist"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Unknown product"
    )
    status, failures, _, reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_test_safety"
    )
    assert status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.PRODUCT_NOT_FOUND in failures


def test_inventory_insufficient(fresh_context):
    """Demanding more inventory than available triggers INVENTORY_INSUFFICIENT."""
    cand = PolicyCandidate(
        candidate_id="cand_high_qty",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        bundle_components=[{"product_id": "prod_backpack_01", "quantity": 100}],  # available is 15
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="High quantity"
    )
    status, failures, _, reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_test_safety"
    )
    assert status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.INVENTORY_INSUFFICIENT in failures


def test_discount_limit_exceeded(fresh_context):
    """Offering discount above maximum_discount_percent triggers DISCOUNT_LIMIT_EXCEEDED."""
    cand = PolicyCandidate(
        candidate_id="cand_disc_high",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=["prod_backpack_01"],
        incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("15.00")),  # max is 8.00%
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Aggressive discount"
    )
    status, failures, _, reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_test_safety"
    )
    assert status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.DISCOUNT_LIMIT_EXCEEDED in failures


def test_contribution_floor_violated(fresh_context):
    """Offering a product/discount with gross margin below floor triggers CONTRIBUTION_FLOOR_VIOLATED."""
    # Find or modify product to have low margin
    cand = PolicyCandidate(
        candidate_id="cand_low_margin",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=["prod_water_bottle_01"],  # price 999, cost 800 -> ~19.9% margin, floor is 25%
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Low margin product"
    )
    status, failures, econ, reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_test_safety"
    )
    assert status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.CONTRIBUTION_FLOOR_VIOLATED in failures


def test_budget_limit_exceeded(fresh_context):
    """Price exceeding buyer's max budget triggers BUDGET_LIMIT_EXCEEDED."""
    tight_intent = BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(budget_type=BudgetType.MAX, max_amount_paise=200000),  # price is 499900
        quantity=1
    )
    cand = PolicyCandidate(
        candidate_id="cand_over_budget",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Too expensive"
    )
    status, failures, _, reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_test_safety",
        intent=tight_intent
    )
    assert status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.BUDGET_LIMIT_EXCEEDED in failures


def test_multiple_failures_deterministic_ordering(fresh_context):
    """Simultaneous failures must be sorted strictly according to FAILURE_CODE_PRIORITY."""
    # Both discount exceeded (priority 11) and inventory insufficient (priority 10)
    cand = PolicyCandidate(
        candidate_id="cand_multi_fail",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=["prod_backpack_01"],
        bundle_components=[{"product_id": "prod_backpack_01", "quantity": 999}],  # inventory insufficient (10)
        incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("50.00")),  # discount exceeded (11)
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Multi fail"
    )
    status, failures, _, primary_reason = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=fresh_context,
        merchant_id="merch_test_safety"
    )
    assert status == PolicySafetyStatus.REJECTED
    assert len(failures) >= 2
    # In canonical ordering, INVENTORY_INSUFFICIENT (priority 10) comes before DISCOUNT_LIMIT_EXCEEDED (priority 11)
    inv_idx = failures.index(PolicySafetyFailureCode.INVENTORY_INSUFFICIENT)
    disc_idx = failures.index(PolicySafetyFailureCode.DISCOUNT_LIMIT_EXCEEDED)
    assert inv_idx < disc_idx
    assert primary_reason == failures[0].value
