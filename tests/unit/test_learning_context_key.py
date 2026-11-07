"""Unit tests for BuyerContextKeyBuilder and demographic privacy safeguards."""

import pytest
from domain.intent_schemas import (
    BuyerIntent,
    BudgetConstraint,
    AttributeRequirement,
    AttributePreference,
    ExclusionConstraint,
    OperatorType
)
from services.learning.context_key import BuyerContextKeyBuilder
from services.learning.errors import SecurityBoundaryError


def test_context_key_deterministic_and_reproducible():
    """Identical buyer intent produces the exact same context key every time."""
    intent = BuyerIntent(
        budget=BudgetConstraint(max_amount_paise=350000, currency="INR"),
        requirements=[
            AttributeRequirement(attribute="laptop_size", operator=OperatorType.GTE, value=15.6)
        ],
        preferences=[
            AttributePreference(attribute="warranty", preference="extended warranty")
        ]
    )

    k1 = BuyerContextKeyBuilder.build_key(intent, category="travel_backpack")
    k2 = BuyerContextKeyBuilder.build_key(intent, category="travel_backpack")
    k3 = BuyerContextKeyBuilder.build_key(intent, category="travel_backpack")

    assert k1 == k2 == k3
    assert k1.startswith("bck_travel_backpack_TIER_MID_2K_4K_")


def test_context_key_order_invariance():
    """Varying order of requirements or preferences produces identical context key."""
    intent_a = BuyerIntent(
        budget=BudgetConstraint(max_amount_paise=450000, currency="INR"),
        requirements=[
            AttributeRequirement(attribute="laptop_size", operator=OperatorType.GTE, value=15.6),
            AttributeRequirement(attribute="water_resistant", operator=OperatorType.EQ, value=True)
        ],
        preferences=[
            AttributePreference(attribute="warranty", preference="24 mo"),
            AttributePreference(attribute="delivery", preference="express")
        ]
    )

    intent_b = BuyerIntent(
        budget=BudgetConstraint(max_amount_paise=450000, currency="INR"),
        requirements=[
            AttributeRequirement(attribute="water_resistant", operator=OperatorType.EQ, value=True),
            AttributeRequirement(attribute="laptop_size", operator=OperatorType.GTE, value=15.6)
        ],
        preferences=[
            AttributePreference(attribute="delivery", preference="express"),
            AttributePreference(attribute="warranty", preference="24 mo")
        ]
    )

    key_a = BuyerContextKeyBuilder.build_key(intent_a)
    key_b = BuyerContextKeyBuilder.build_key(intent_b)

    assert key_a == key_b


def test_context_key_rejects_demographic_attributes():
    """Strictly rejects attempts to profile buyers on age, gender, income, religion, etc."""
    intent_age = BuyerIntent(
        budget=BudgetConstraint(max_amount_paise=400000, currency="INR"),
        requirements=[
            AttributeRequirement(attribute="age", operator=OperatorType.GTE, value=25)
        ]
    )
    with pytest.raises(SecurityBoundaryError) as exc_age:
        BuyerContextKeyBuilder.build_key(intent_age)
    assert "Forbidden demographic attribute 'age'" in str(exc_age.value)

    intent_income = BuyerIntent(
        budget=BudgetConstraint(max_amount_paise=400000, currency="INR"),
        preferences=[
            AttributePreference(attribute="income", preference="high_income")
        ]
    )
    with pytest.raises(SecurityBoundaryError) as exc_income:
        BuyerContextKeyBuilder.build_key(intent_income)
    assert "Forbidden demographic attribute 'income'" in str(exc_income.value)
