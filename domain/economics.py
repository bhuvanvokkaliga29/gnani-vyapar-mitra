"""Deterministic Commercial Economics & Financial Calculations.

Zero floating-point arithmetic. All monetary values are represented in integer
minor units (paise). All percentages and rates are calculated using Python's
exact Decimal arithmetic.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple, Optional, List, Dict, Any
from dataclasses import dataclass


def calculate_gross_profit(price_paise: int, cost_paise: int) -> int:
    """Calculate gross profit in integer paise.

    Formula: gross_profit = selling_price - COGS
    """
    if price_paise < 0 or cost_paise < 0:
        raise ValueError("Price and cost must be non-negative integers")
    return price_paise - cost_paise


def calculate_gross_margin_percent(price_paise: int, cost_paise: int) -> Decimal:
    """Calculate gross margin percentage using exact Decimal arithmetic.

    Formula: gross_margin_percent = ((price - cost) / price) * 100
    """
    if price_paise <= 0:
        raise ValueError("Selling price must be greater than zero to compute margin percentage")
    if cost_paise < 0:
        raise ValueError("Cost cannot be negative")

    price_dec = Decimal(price_paise)
    cost_dec = Decimal(cost_paise)

    margin = ((price_dec - cost_dec) / price_dec) * Decimal(100)
    # Quantize to 2 decimal places for standard financial reporting
    return margin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_available_to_sell(inventory_quantity: int, reserved_quantity: int = 0) -> int:
    """Determine available physical units eligible for immediate commercial sale.

    Formula: available_to_sell = inventory_quantity - reserved_quantity
    """
    if inventory_quantity < 0:
        raise ValueError("Inventory quantity cannot be negative")
    if reserved_quantity < 0:
        raise ValueError("Reserved quantity cannot be negative")
    if reserved_quantity > inventory_quantity:
        raise ValueError("Reserved quantity cannot exceed total inventory quantity")

    return inventory_quantity - reserved_quantity


def is_product_eligible(
    price_paise: int,
    cost_paise: int,
    inventory_quantity: int,
    reserved_quantity: int = 0,
    is_active: bool = True,
    minimum_margin_percent: Optional[Decimal] = None
) -> Tuple[bool, Optional[str]]:
    """Deterministic eligibility check for a catalog product.

    A product is eligible to be offered if:
    1. It is active.
    2. It has available stock to sell (> 0).
    3. Selling price > 0.
    4. Unit gross margin satisfies merchant floor (if configured).
    """
    if not is_active:
        return False, "Product is currently inactive"

    try:
        available = calculate_available_to_sell(inventory_quantity, reserved_quantity)
    except ValueError as e:
        return False, str(e)

    if available <= 0:
        return False, "Insufficient inventory available to sell"

    if price_paise <= 0:
        return False, "Price must be strictly positive"

    if minimum_margin_percent is not None:
        margin = calculate_gross_margin_percent(price_paise, cost_paise)
        if margin < minimum_margin_percent:
            return False, f"Product margin {margin}% is below minimum required margin {minimum_margin_percent}%"

    return True, None


@dataclass(frozen=True)
class BasketItem:
    product_id: str
    quantity: int
    unit_price_paise: int
    unit_cost_paise: int


@dataclass(frozen=True)
class BasketEconomics:
    gross_revenue_paise: int
    total_cogs_paise: int
    gross_profit_paise: int
    gross_margin_percent: Decimal
    promotional_discount_paise: int
    effective_discount_percent: Decimal
    is_compliant: bool
    violation_reasons: List[str]


def evaluate_basket_economics(
    items: List[BasketItem],
    promotional_discount_paise: int = 0,
    minimum_margin_percent: Optional[Decimal] = None,
    maximum_discount_percent: Optional[Decimal] = None
) -> BasketEconomics:
    """Evaluate full basket commercial economics and deterministic financial guardrails.

    Calculates:
    - Baseline catalog revenue (sum of regular unit prices * quantity)
    - Net gross revenue (baseline - promotional discount)
    - Total COGS (sum of unit costs * quantity)
    - Effective discount percentage
    - Basket gross margin percentage
    - Compliance against merchant margin floor and discount ceiling
    """
    if not items:
        raise ValueError("Basket must contain at least one item")
    if promotional_discount_paise < 0:
        raise ValueError("Promotional discount cannot be negative")

    baseline_revenue = sum(item.unit_price_paise * item.quantity for item in items)
    total_cogs = sum(item.unit_cost_paise * item.quantity for item in items)

    net_revenue = baseline_revenue - promotional_discount_paise
    if net_revenue <= 0:
        raise ValueError("Net basket revenue must be strictly positive")

    gross_profit = net_revenue - total_cogs

    # Exact decimal percentage calculations
    net_rev_dec = Decimal(net_revenue)
    base_rev_dec = Decimal(baseline_revenue)
    cogs_dec = Decimal(total_cogs)
    disc_dec = Decimal(promotional_discount_paise)

    basket_margin_pct = (((net_rev_dec - cogs_dec) / net_rev_dec) * Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    effective_disc_pct = ((disc_dec / base_rev_dec) * Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    violations: List[str] = []

    if minimum_margin_percent is not None and basket_margin_pct < minimum_margin_percent:
        violations.append(
            f"Basket gross margin {basket_margin_pct}% violates minimum margin floor {minimum_margin_percent}%"
        )

    if maximum_discount_percent is not None and effective_disc_pct > maximum_discount_percent:
        violations.append(
            f"Effective discount {effective_disc_pct}% exceeds maximum discount ceiling {maximum_discount_percent}%"
        )

    return BasketEconomics(
        gross_revenue_paise=net_revenue,
        total_cogs_paise=total_cogs,
        gross_profit_paise=gross_profit,
        gross_margin_percent=basket_margin_pct,
        promotional_discount_paise=promotional_discount_paise,
        effective_discount_percent=effective_disc_pct,
        is_compliant=len(violations) == 0,
        violation_reasons=violations
    )
