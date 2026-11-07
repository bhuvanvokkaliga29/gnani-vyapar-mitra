"""Unit tests for deterministic commercial economics layer."""

import pytest
from decimal import Decimal
from domain.economics import (
    calculate_gross_profit,
    calculate_gross_margin_percent,
    calculate_available_to_sell,
    is_product_eligible,
    BasketItem,
    evaluate_basket_economics
)


def test_gross_profit_calculation():
    """Verify integer paise gross profit calculation."""
    profit = calculate_gross_profit(price_paise=299900, cost_paise=180000)
    assert profit == 119900
    assert isinstance(profit, int)


def test_negative_values_rejected_in_profit():
    """Negative prices or costs must be rejected."""
    with pytest.raises(ValueError, match="non-negative"):
        calculate_gross_profit(price_paise=-100, cost_paise=50)

    with pytest.raises(ValueError, match="non-negative"):
        calculate_gross_profit(price_paise=100, cost_paise=-50)


def test_gross_margin_percent_precision():
    """Verify exact decimal gross margin calculation with no float errors."""
    # (2999 - 1800) / 2999 = 1199 / 2999 = 39.97999... -> 39.98%
    margin = calculate_gross_margin_percent(price_paise=299900, cost_paise=180000)
    assert margin == Decimal("39.98")
    assert isinstance(margin, Decimal)

    # 100% margin when COGS = 0
    assert calculate_gross_margin_percent(price_paise=1000, cost_paise=0) == Decimal("100.00")

    # 0% margin when price = cost
    assert calculate_gross_margin_percent(price_paise=5000, cost_paise=5000) == Decimal("0.00")

    # Negative margin when cost > price
    assert calculate_gross_margin_percent(price_paise=1000, cost_paise=1500) == Decimal("-50.00")


def test_zero_or_negative_price_rejected_in_margin():
    """Zero or negative selling prices must raise ValueError."""
    with pytest.raises(ValueError, match="greater than zero"):
        calculate_gross_margin_percent(price_paise=0, cost_paise=100)

    with pytest.raises(ValueError, match="greater than zero"):
        calculate_gross_margin_percent(price_paise=-500, cost_paise=100)


def test_available_to_sell():
    """Verify inventory quantity minus reserved quantity."""
    assert calculate_available_to_sell(inventory_quantity=30, reserved_quantity=5) == 25
    assert calculate_available_to_sell(inventory_quantity=10, reserved_quantity=10) == 0

    with pytest.raises(ValueError, match="cannot exceed total"):
        calculate_available_to_sell(inventory_quantity=5, reserved_quantity=10)

    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_available_to_sell(inventory_quantity=-1, reserved_quantity=0)


def test_product_eligibility():
    """Verify deterministic product eligibility rules."""
    # Eligible standard product
    is_elig, reason = is_product_eligible(
        price_paise=299900,
        cost_paise=180000,
        inventory_quantity=30,
        reserved_quantity=0,
        is_active=True,
        minimum_margin_percent=Decimal("25.00")
    )
    assert is_elig is True
    assert reason is None

    # Inactive product
    is_elig, reason = is_product_eligible(
        price_paise=1000,
        cost_paise=500,
        inventory_quantity=10,
        is_active=False
    )
    assert is_elig is False
    assert "inactive" in reason

    # Out of stock product
    is_elig, reason = is_product_eligible(
        price_paise=1000,
        cost_paise=500,
        inventory_quantity=5,
        reserved_quantity=5,
        is_active=True
    )
    assert is_elig is False
    assert "Insufficient inventory" in reason

    # Margin below floor
    is_elig, reason = is_product_eligible(
        price_paise=10000,
        cost_paise=8500,  # 15% margin
        inventory_quantity=10,
        minimum_margin_percent=Decimal("20.00")
    )
    assert is_elig is False
    assert "below minimum required margin" in reason


def test_basket_economics_and_guardrails():
    """Verify basket evaluation with discount and margin compliance checks."""
    items = [
        BasketItem(product_id="p1", quantity=1, unit_price_paise=299900, unit_cost_paise=180000),
        BasketItem(product_id="p2", quantity=1, unit_price_paise=79900, unit_cost_paise=35000)
    ]
    # Baseline: 299900 + 79900 = 379800 paise
    # Total COGS: 180000 + 35000 = 215000 paise

    # Case A: Compliant bundle with 5% discount (18990 paise)
    econ = evaluate_basket_economics(
        items=items,
        promotional_discount_paise=18990,
        minimum_margin_percent=Decimal("25.00"),
        maximum_discount_percent=Decimal("8.00")
    )
    assert econ.is_compliant is True
    assert econ.effective_discount_percent == Decimal("5.00")
    assert econ.gross_profit_paise == (379800 - 18990) - 215000

    # Case B: Exceeds discount ceiling (10% discount > 8% max)
    econ_disc_viol = evaluate_basket_economics(
        items=items,
        promotional_discount_paise=37980,  # 10%
        minimum_margin_percent=Decimal("25.00"),
        maximum_discount_percent=Decimal("8.00")
    )
    assert econ_disc_viol.is_compliant is False
    assert any("exceeds maximum discount ceiling" in r for r in econ_disc_viol.violation_reasons)
