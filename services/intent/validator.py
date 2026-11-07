"""Semantic Validation and Internal Contradiction Detection for BuyerIntent."""

from typing import List, Optional
from domain.intent_schemas import (
    BuyerIntent,
    IntentConflict,
    ConfidenceLevel,
    BudgetConstraint,
    BudgetType
)


class IntentValidationError(Exception):
    """Raised when an intent payload fails semantic validation."""
    pass


def validate_and_enrich_intent(intent: BuyerIntent) -> BuyerIntent:
    """Perform post-extraction semantic validation, conflict detection, and unknown enumeration."""

    # 1. Budget Sanity Validation
    if intent.budget:
        b = intent.budget
        if b.amount_paise is not None and b.amount_paise <= 0:
            raise IntentValidationError("Budget amount must be strictly positive")
        if b.min_amount_paise is not None and b.min_amount_paise < 0:
            raise IntentValidationError("Minimum budget cannot be negative")
        if b.max_amount_paise is not None and b.max_amount_paise <= 0:
            raise IntentValidationError("Maximum budget must be strictly positive")
        if b.min_amount_paise is not None and b.max_amount_paise is not None:
            if b.min_amount_paise > b.max_amount_paise:
                raise IntentValidationError("Minimum budget cannot exceed maximum budget")

    # 2. Contradiction Detection: Exclusion vs Preference Collision
    pref_values = {p.preference.lower() for p in intent.preferences}
    for excl in intent.exclusions:
        if excl.excluded_value.lower() in pref_values:
            conflict = IntentConflict(
                field=excl.attribute,
                previous_value=excl.excluded_value,
                new_value=f"excluded {excl.excluded_value}",
                reason=f"Buyer simultaneously preferred and excluded '{excl.excluded_value}'"
            )
            intent.conflicts.append(conflict)
            intent.needs_clarification = True
            intent.clarification_questions.append(
                f"Did you want {excl.excluded_value} included or excluded?"
            )

    # 3. Explicit Missing Information (Unknowns Enumeration)
    unknowns: List[str] = []

    if not intent.category:
        unknowns.append("category")
        intent.needs_clarification = True
        if not intent.clarification_questions:
            intent.clarification_questions.append("What type of product are you looking for?")

    if not intent.budget:
        unknowns.append("budget")

    # If it's a laptop bag or sleeve, check if laptop size is known
    if intent.category in ["travel_backpack", "laptop_backpack", "laptop_sleeve"]:
        has_laptop_size = any(r.attribute == "laptop_size" for r in intent.requirements)
        if not has_laptop_size:
            unknowns.append("laptop_size")

    intent.unknowns = sorted(list(set(intent.unknowns + unknowns)))

    # 4. Confidence Calibration
    if intent.conflicts:
        intent.confidence = ConfidenceLevel.LOW
        intent.needs_clarification = True
    elif len(intent.unknowns) >= 3 or not intent.category:
        intent.confidence = ConfidenceLevel.MEDIUM
    else:
        intent.confidence = ConfidenceLevel.HIGH

    return intent
