"""Unit tests for semantic validation and conflict detection."""

import pytest
from domain.intent_schemas import (
    BuyerIntent,
    BudgetConstraint,
    BudgetType,
    ConstraintType,
    AttributePreference,
    ExclusionConstraint,
    ConfidenceLevel
)
from services.intent.validator import validate_and_enrich_intent, IntentValidationError


def test_invalid_budget_bounds():
    """Verify negative budget amounts or min > max raise IntentValidationError."""
    with pytest.raises(IntentValidationError, match="strictly positive"):
        intent = BuyerIntent(budget=BudgetConstraint(max_amount_paise=0))
        validate_and_enrich_intent(intent)

    with pytest.raises(ValueError):  # Pydantic model validator catches min > max
        BudgetConstraint(min_amount_paise=5000, max_amount_paise=2000)


def test_contradiction_detection_preference_vs_exclusion():
    """Verify simultaneous preference and exclusion of same attribute flags a conflict."""
    intent = BuyerIntent(
        category="travel_backpack",
        preferences=[AttributePreference(attribute="material", preference="leather")],
        exclusions=[ExclusionConstraint(attribute="material", excluded_value="leather")]
    )

    enriched = validate_and_enrich_intent(intent)
    assert enriched.needs_clarification is True
    assert len(enriched.conflicts) == 1
    assert enriched.conflicts[0].field == "material"
    assert enriched.confidence == ConfidenceLevel.LOW
    assert len(enriched.clarification_questions) > 0


def test_unknowns_enumeration():
    """Verify missing critical fields are accurately tracked in unknowns."""
    # When buyer specifies only category
    intent = BuyerIntent(category="travel_backpack")
    enriched = validate_and_enrich_intent(intent)

    # Budget and laptop_size should be explicitly tracked as unknowns
    assert "budget" in enriched.unknowns
    assert "laptop_size" in enriched.unknowns
    assert enriched.confidence == ConfidenceLevel.HIGH

    # When category itself is missing
    vague_intent = BuyerIntent()
    vague_enriched = validate_and_enrich_intent(vague_intent)
    assert "category" in vague_enriched.unknowns
    assert vague_enriched.needs_clarification is True
    assert vague_enriched.confidence == ConfidenceLevel.MEDIUM
