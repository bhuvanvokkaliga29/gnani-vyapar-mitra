"""Unit tests for Phase 6 EligibilityFilter."""

import pytest
from domain.intent_schemas import (
    BuyerIntent,
    BudgetConstraint,
    AttributeRequirement,
    ExclusionConstraint,
    OperatorType
)
from services.buyer_lab.schemas import BuyerOffer, OfferRejectionCode
from services.buyer_lab.filter import EligibilityFilter


@pytest.fixture
def filter_engine():
    return EligibilityFilter()


@pytest.fixture
def valid_offer():
    return BuyerOffer(
        offer_id="off_valid",
        merchant_id="merch_atlas",
        merchant_label="Atlas",
        product_id="prod_1",
        product_name="Atlas Nylon Travel Pack",
        price_paise=299900,
        currency="INR",
        availability=True,
        relevant_attributes={"laptop_size": 15.6, "capacity_liters": 28.0, "material": "nylon"},
        included_items=["laptop_sleeve"]
    )


def test_availability_filter(filter_engine, valid_offer):
    """Unavailable or out-of-stock offers are rejected."""
    valid_offer.availability = False
    intent = BuyerIntent()
    eligible, rejected, traces, checked = filter_engine.filter_offers(intent, [valid_offer])

    assert len(eligible) == 0
    assert len(rejected) == 1
    assert rejected[0].rejection_reason == OfferRejectionCode.UNAVAILABLE


def test_budget_ceiling_filter(filter_engine, valid_offer):
    """Offers exceeding stated budget ceiling are rejected."""
    intent = BuyerIntent(budget=BudgetConstraint(max_amount_paise=250000, currency="INR"))
    eligible, rejected, traces, checked = filter_engine.filter_offers(intent, [valid_offer])

    assert len(eligible) == 0
    assert len(rejected) == 1
    assert rejected[0].rejection_reason == OfferRejectionCode.BUDGET_EXCEEDED


def test_currency_mismatch_filter(filter_engine, valid_offer):
    """Offers in foreign currency are rejected."""
    valid_offer.currency = "USD"
    intent = BuyerIntent(budget=BudgetConstraint(max_amount_paise=500000, currency="INR"))
    eligible, rejected, traces, checked = filter_engine.filter_offers(intent, [valid_offer])

    assert len(eligible) == 0
    assert len(rejected) == 1
    assert rejected[0].rejection_reason == OfferRejectionCode.CURRENCY_MISMATCH


def test_hard_requirement_numeric_operators(filter_engine, valid_offer):
    """Hard numeric requirements (GTE, LTE) are correctly evaluated."""
    # Requirement: laptop_size >= 16.0 (Offer is 15.6) -> FAIL
    intent_gte = BuyerIntent(
        requirements=[AttributeRequirement(attribute="laptop_size", operator=OperatorType.GTE, value=16.0)]
    )
    eligible, rejected, _, _ = filter_engine.filter_offers(intent_gte, [valid_offer])
    assert len(eligible) == 0
    assert rejected[0].rejection_reason == OfferRejectionCode.HARD_REQUIREMENT_VIOLATED

    # Requirement: laptop_size <= 15.6 (Offer is 15.6) -> PASS
    intent_lte = BuyerIntent(
        requirements=[AttributeRequirement(attribute="laptop_size", operator=OperatorType.LTE, value=15.6)]
    )
    eligible, rejected, _, _ = filter_engine.filter_offers(intent_lte, [valid_offer])
    assert len(eligible) == 1


def test_hard_requirement_string_operators(filter_engine, valid_offer):
    """String operators (CONTAINS, EQ, NEQ) are correctly evaluated."""
    # Material CONTAINS 'nylon' -> PASS
    intent_contains = BuyerIntent(
        requirements=[AttributeRequirement(attribute="material", operator=OperatorType.CONTAINS, value="nylon")]
    )
    eligible, rejected, _, _ = filter_engine.filter_offers(intent_contains, [valid_offer])
    assert len(eligible) == 1

    # Material EQ 'leather' -> FAIL
    intent_eq = BuyerIntent(
        requirements=[AttributeRequirement(attribute="material", operator=OperatorType.EQ, value="leather")]
    )
    eligible, rejected, _, _ = filter_engine.filter_offers(intent_eq, [valid_offer])
    assert len(eligible) == 0
    assert rejected[0].rejection_reason == OfferRejectionCode.HARD_REQUIREMENT_VIOLATED


def test_explicit_exclusion_filter(filter_engine, valid_offer):
    """Explicit exclusions strictly filter out matching materials, colors, or terms."""
    # Exclude nylon
    intent = BuyerIntent(
        exclusions=[ExclusionConstraint(attribute="material", excluded_value="nylon")]
    )
    eligible, rejected, _, _ = filter_engine.filter_offers(intent, [valid_offer])
    assert len(eligible) == 0
    assert rejected[0].rejection_reason == OfferRejectionCode.EXCLUDED_BY_BUYER


def test_exclusion_in_accessory(filter_engine, valid_offer):
    """Exclusion in included accessory items is strictly caught."""
    valid_offer.included_items = ["genuine_leather_strap"]
    intent = BuyerIntent(
        exclusions=[ExclusionConstraint(attribute="material", excluded_value="leather")]
    )
    eligible, rejected, _, _ = filter_engine.filter_offers(intent, [valid_offer])
    assert len(eligible) == 0
    assert rejected[0].rejection_reason == OfferRejectionCode.EXCLUDED_BY_BUYER
