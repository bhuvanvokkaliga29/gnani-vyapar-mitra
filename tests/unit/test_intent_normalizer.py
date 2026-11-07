"""Unit tests for deterministic intent normalization layer."""

import pytest
from domain.intent_schemas import BudgetType, ConstraintType, OperatorType
from services.intent.normalizer import (
    extract_budget,
    extract_laptop_size,
    extract_quantity,
    extract_exclusions,
    extract_preferences_and_requirements,
    extract_category_and_use_case,
    extract_temporal,
    parse_raw_amount_to_paise
)


def test_parse_raw_amount_to_paise():
    """Verify conversion of various amount expressions into integer paise."""
    assert parse_raw_amount_to_paise("5000") == 500000
    assert parse_raw_amount_to_paise("₹5,000") == 500000
    assert parse_raw_amount_to_paise("5k") == 500000
    assert parse_raw_amount_to_paise("2.5k") == 250000
    assert parse_raw_amount_to_paise("1000 inr") == 100000
    assert parse_raw_amount_to_paise("invalid") is None


def test_extract_budget_ranges_and_approximations():
    """Verify budget extraction across max, range, and approximate types."""
    # 1. Range
    res_range = extract_budget("Need something between 3k and 5k")
    assert res_range is not None
    b_range, src = res_range
    assert b_range.budget_type == BudgetType.RANGE
    assert b_range.min_amount_paise == 300000
    assert b_range.max_amount_paise == 500000

    # 2. Approximate
    res_approx = extract_budget("Budget is around ₹5,000")
    assert res_approx is not None
    b_approx, src = res_approx
    assert b_approx.budget_type == BudgetType.APPROXIMATE
    assert b_approx.amount_paise == 500000

    # 3. Soft preference
    res_soft = extract_budget("Prefer under 4000")
    assert res_soft is not None
    b_soft, src = res_soft
    assert b_soft.constraint_type == ConstraintType.SOFT
    assert b_soft.max_amount_paise == 400000

    # 4. Word numbers
    res_words = extract_budget("I have five thousand rupees to spend")
    assert res_words is not None
    b_words, src = res_words
    assert b_words.max_amount_paise == 500000


def test_extract_laptop_size():
    """Verify extraction of laptop screen sizes."""
    assert extract_laptop_size("for a 15-inch laptop")[0] == 15.0
    assert extract_laptop_size("fits 16 inch macbook")[0] == 16.0
    assert extract_laptop_size("need a 14\" sleeve")[0] == 14.0
    assert extract_laptop_size("no laptop mentioned") is None


def test_extract_quantity():
    """Verify extraction of item quantities."""
    assert extract_quantity("I need two backpacks")[0] == 2
    assert extract_quantity("buy 3 units")[0] == 3
    assert extract_quantity("a couple of sleeves")[0] == 2
    assert extract_quantity("just looking around") is None


def test_extract_exclusions():
    """Verify extraction of negative constraints."""
    excls = extract_exclusions("I need a backpack, no leather and not red")
    assert len(excls) == 2
    assert excls[0][0].attribute == "material"
    assert excls[0][0].excluded_value == "leather"
    assert excls[1][0].attribute == "color"
    assert excls[1][0].excluded_value == "red"


def test_requirements_vs_preferences_separation():
    """Verify that must-haves become requirements and nice-to-haves become preferences."""
    text = "It must fit a 15-inch laptop, and I'd prefer something lightweight."
    reqs, prefs = extract_preferences_and_requirements(text)

    # 15-inch laptop must be a requirement
    assert len(reqs) == 1
    assert reqs[0][0].attribute == "laptop_size"
    assert reqs[0][0].value == 15.0
    assert reqs[0][0].importance == "required"

    # Lightweight must be a preference
    assert len(prefs) == 1
    assert prefs[0][0].attribute == "weight"
    assert prefs[0][0].preference == "lightweight"
    assert prefs[0][0].strength.value == "preferred"


def test_extract_temporal():
    """Verify extraction of delivery deadlines."""
    temp = extract_temporal("I need it by Friday for my flight")
    assert temp is not None
    assert temp[0].delivery_deadline == "Friday"
