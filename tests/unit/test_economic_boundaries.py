"""Economic Boundary and Invariant Monotonicity Tests."""

import pytest
from decimal import Decimal
from domain.economics import (
    calculate_gross_profit,
    calculate_gross_margin_percent,
    evaluate_basket_economics,
    BasketItem
)
from domain.commerce_schemas import (
    MerchantCreateRequest,
    ConstraintsUpdateRequest,
    RelationshipCreateRequest
)
from pydantic import ValidationError


def test_margin_floor_exact_boundary():
    """Test exact margin floor threshold: 24.99% (Reject), 25.00% (Accept), 25.01% (Accept)."""
    # 1. 24.99% margin: Price 10000 paise, Cost 7501 paise -> Margin = 24.99%
    items_2499 = [BasketItem(product_id="p1", quantity=1, unit_price_paise=10000, unit_cost_paise=7501)]
    econ_2499 = evaluate_basket_economics(
        items=items_2499,
        promotional_discount_paise=0,
        minimum_margin_percent=Decimal("25.00")
    )
    assert econ_2499.gross_margin_percent == Decimal("24.99")
    assert econ_2499.is_compliant is False

    # 2. 25.00% margin: Price 10000 paise, Cost 7500 paise -> Margin = 25.00%
    items_2500 = [BasketItem(product_id="p1", quantity=1, unit_price_paise=10000, unit_cost_paise=7500)]
    econ_2500 = evaluate_basket_economics(
        items=items_2500,
        promotional_discount_paise=0,
        minimum_margin_percent=Decimal("25.00")
    )
    assert econ_2500.gross_margin_percent == Decimal("25.00")
    assert econ_2500.is_compliant is True

    # 3. 25.01% margin: Price 10000 paise, Cost 7499 paise -> Margin = 25.01%
    items_2501 = [BasketItem(product_id="p1", quantity=1, unit_price_paise=10000, unit_cost_paise=7499)]
    econ_2501 = evaluate_basket_economics(
        items=items_2501,
        promotional_discount_paise=0,
        minimum_margin_percent=Decimal("25.00")
    )
    assert econ_2501.gross_margin_percent == Decimal("25.01")
    assert econ_2501.is_compliant is True


def test_discount_ceiling_exact_boundary():
    """Test exact discount ceiling threshold: 8.00% (Accept), 8.01% (Reject)."""
    # Baseline: 100,000 paise (₹1,000)
    items = [BasketItem(product_id="p1", quantity=1, unit_price_paise=100000, unit_cost_paise=50000)]

    # 1. 8.00% discount: 8,000 paise -> Accept
    econ_800 = evaluate_basket_economics(
        items=items,
        promotional_discount_paise=8000,
        maximum_discount_percent=Decimal("8.00")
    )
    assert econ_800.effective_discount_percent == Decimal("8.00")
    assert econ_800.is_compliant is True

    # 2. 8.01% discount: 8,010 paise -> Reject
    econ_801 = evaluate_basket_economics(
        items=items,
        promotional_discount_paise=8010,
        maximum_discount_percent=Decimal("8.00")
    )
    assert econ_801.effective_discount_percent == Decimal("8.01")
    assert econ_801.is_compliant is False
    assert any("exceeds maximum discount ceiling" in r for r in econ_801.violation_reasons)


def test_economic_monotonicity_invariants():
    """Verify monotonic invariants of price, cost, and discount changes."""
    base_price = 10000
    base_cost = 6000
    base_profit = calculate_gross_profit(base_price, base_cost)

    # Invariant 1: Price decreases while cost is unchanged -> profit must strictly decrease
    lower_price = base_price - 500
    lower_profit = calculate_gross_profit(lower_price, base_cost)
    assert lower_profit < base_profit

    # Invariant 2: Cost increases while price is unchanged -> profit must strictly decrease
    higher_cost = base_cost + 500
    higher_cost_profit = calculate_gross_profit(base_price, higher_cost)
    assert higher_cost_profit < base_profit

    # Invariant 3: Promotional discount increases -> net revenue and profit must decrease
    items = [BasketItem(product_id="p1", quantity=1, unit_price_paise=base_price, unit_cost_paise=base_cost)]
    econ_low_disc = evaluate_basket_economics(items, promotional_discount_paise=100)
    econ_high_disc = evaluate_basket_economics(items, promotional_discount_paise=500)
    assert econ_high_disc.gross_profit_paise < econ_low_disc.gross_profit_paise
    assert econ_high_disc.gross_revenue_paise < econ_low_disc.gross_revenue_paise


def test_merchant_objective_enums():
    """Verify all four valid objectives are accepted and arbitrary strings are rejected."""
    for valid_obj in ["MAXIMIZE_REVENUE", "MAXIMIZE_CONTRIBUTION", "INCREASE_AOV", "BALANCE_REVENUE_AND_MARGIN"]:
        req = MerchantCreateRequest(id="merch_1", name="Merchant 1", business_objective=valid_obj)
        assert req.business_objective == valid_obj

    # Invalid objective must raise ValidationError
    with pytest.raises(ValidationError):
        MerchantCreateRequest(id="merch_1", name="Merchant 1", business_objective="INVALID_OBJECTIVE_XYZ")

    with pytest.raises(ValidationError):
        ConstraintsUpdateRequest(business_objective="ARBITRARY_GOAL")


def test_relationship_type_enums():
    """Verify all five valid relationship types are accepted and invalid types are rejected."""
    for valid_type in ["COMPLEMENTARY", "SUBSTITUTE", "BUNDLE_COMPONENT", "UPSELL", "CROSS_SELL"]:
        req = RelationshipCreateRequest(
            primary_product_id="prod_1",
            related_product_id="prod_2",
            relationship_type=valid_type
        )
        assert req.relationship_type == valid_type

    # Invalid relationship type must raise ValidationError
    with pytest.raises(ValidationError):
        RelationshipCreateRequest(
            primary_product_id="prod_1",
            related_product_id="prod_2",
            relationship_type="SIBLING_PRODUCT"
        )
