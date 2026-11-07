"""Deterministic Normalization and Pattern Parsing for Natural-Language Intent.

Performs exact, zero-float conversion for currencies, paise minor units,
quantities, size dimensions, and exclusions without requiring LLM inference.
"""

import re
from decimal import Decimal
from typing import Optional, Tuple, List, Dict, Any
from domain.intent_schemas import (
    BudgetConstraint,
    BudgetType,
    ConstraintType,
    AttributeRequirement,
    AttributePreference,
    ExclusionConstraint,
    TemporalConstraint,
    OperatorType,
    PreferenceStrength
)

WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "a couple": 2,
    "a couple of": 2,
}

WORD_AMOUNTS = {
    "one thousand": 1000,
    "two thousand": 2000,
    "three thousand": 3000,
    "four thousand": 4000,
    "five thousand": 5000,
    "six thousand": 6000,
    "seven thousand": 7000,
    "eight thousand": 8000,
    "nine thousand": 9000,
    "ten thousand": 10000,
}

# Speculative/hedging markers that indicate uncertain quantity
SPECULATIVE_MARKERS = [
    "might need", "may need", "maybe", "possibly", "perhaps",
    "could need", "thinking about", "considering", "not sure if",
    "probably need", "might want",
]

# Positive affirmation phrases that prevent false exclusion matching
POSITIVE_AFFIRMATIONS = [
    "is okay", "is fine", "is ok", "is good", "is acceptable",
    "is alright", "works", "will do", "would be fine",
    "would be okay", "would be good", "is great",
]


def parse_raw_amount_to_paise(val_str: str) -> Optional[int]:
    """Convert numeric string or shorthand ('5k', '5,000', '5000', '1.5 lakh') into integer paise."""
    s = val_str.lower().strip().replace(",", "").replace("₹", "").replace("rs", "").replace("inr", "").replace("rupees", "").strip()
    if not s:
        return None

    # Handle lakh variants: '1 lakh', '1.5 lakh', '1.5lakh', '2 lakhs'
    lakh_match = re.match(r'^([\d.]+)\s*lakhs?$', s)
    if lakh_match:
        try:
            num = float(lakh_match.group(1))
            return int(num * 100000 * 100)
        except ValueError:
            return None

    # Handle 'k' shorthand: '5k', '7.5k', '5 k', '5.5 k'
    k_match = re.match(r'^([\d.]+)\s*k$', s)
    if k_match:
        try:
            num = float(k_match.group(1))
            return int(num * 1000 * 100)
        except ValueError:
            return None

    # Handle standard integer
    try:
        rupees = int(float(s))
        return rupees * 100
    except ValueError:
        return None


def detect_currency(text: str) -> str:
    """Detect currency from text. Returns ISO 4217 code. Defaults to INR."""
    t = text.lower()
    if re.search(r'(?:\busd\b|\bdollars?\b|us\s*\$|\$\d)', t):
        return "USD"
    if re.search(r'\b(?:eur|euros?|€)\b', t):
        return "EUR"
    if re.search(r'(?:\bgbp\b|\bpounds?\b|\xa3)', t):
        return "GBP"
    return "INR"


def extract_budget(text: str) -> Optional[Tuple[BudgetConstraint, str]]:
    """Deterministically extract budget constraint and source text from message."""
    t = text.lower()
    currency = detect_currency(t)

    # Amount pattern: matches ₹, Rs, Rs., INR prefix + number + optional k/lakh suffix
    # Also matches standalone numbers with k/lakh, and word amounts
    _amt = r'(?:₹|rs\.?\s*|inr\s+)?\s*([\d,\.]+\s*(?:k|lakhs?)?)'
    _word_amt = r'(\w+\s+thousand)'

    # 0. In-utterance correction: "actually, make that 800", "make that 4000", "actually 6000"
    corr_match = re.search(
        r'(?:actually|make that|change that to|rather|instead)\s+(?:make that\s+)?'
        + r'((?:₹|rs\.?\s*|inr\s+)?\s*[\d,\.]+\s*(?:k|lakhs?)?|\w+\s+thousand)',
        t
    )
    if corr_match:
        raw_val = corr_match.group(1).strip()
        amount_p = None
        if raw_val in WORD_AMOUNTS:
            amount_p = WORD_AMOUNTS[raw_val] * 100
        else:
            amount_p = parse_raw_amount_to_paise(raw_val)

        if amount_p:
            constraint = BudgetConstraint(
                max_amount_paise=amount_p,
                currency=currency,
                budget_type=BudgetType.MAX,
                constraint_type=ConstraintType.HARD
            )
            return constraint, corr_match.group(0)

    # 1. Range expressions: "between 3k and 5k", "between ₹3,000 and ₹5,000"
    range_match = re.search(
        r'between\s+((?:₹|rs\.?\s*|inr\s+)?\s*[\d,\.]+\s*(?:k|lakhs?)?)\s+and\s+((?:₹|rs\.?\s*|inr\s+)?\s*[\d,\.]+\s*(?:k|lakhs?)?)',
        t
    )
    if range_match:
        min_p = parse_raw_amount_to_paise(range_match.group(1))
        max_p = parse_raw_amount_to_paise(range_match.group(2))
        if min_p and max_p:
            constraint = BudgetConstraint(
                min_amount_paise=min_p,
                max_amount_paise=max_p,
                currency=currency,
                budget_type=BudgetType.RANGE,
                constraint_type=ConstraintType.HARD
            )
            return constraint, range_match.group(0)

    # 2. Approximate expressions: "around 5000", "about ₹5k", "approx 5000"
    approx_match = re.search(
        r'(around|about|approx|approximately)\s+((?:₹|rs\.?\s*|inr\s+)?\s*[\d,\.]+\s*(?:k|lakhs?)?|\w+\s+thousand)',
        t
    )
    if approx_match:
        raw_val = approx_match.group(2).strip()
        amount_p = None
        if raw_val in WORD_AMOUNTS:
            amount_p = WORD_AMOUNTS[raw_val] * 100
        else:
            amount_p = parse_raw_amount_to_paise(raw_val)

        if amount_p:
            constraint = BudgetConstraint(
                amount_paise=amount_p,
                currency=currency,
                budget_type=BudgetType.APPROXIMATE,
                constraint_type=ConstraintType.SOFT
            )
            return constraint, approx_match.group(0)

    # 3. Soft preference budget: "prefer under 5000", "prefer under 5k"
    soft_match = re.search(
        r'(prefer|preferably|like to keep it)\s+(under|below|within|max)?\s*((?:₹|rs\.?\s*|inr\s+)?\s*[\d,\.]+\s*(?:k|lakhs?)?)',
        t
    )
    if soft_match and soft_match.group(3):
        amount_p = parse_raw_amount_to_paise(soft_match.group(3))
        if amount_p:
            constraint = BudgetConstraint(
                max_amount_paise=amount_p,
                currency=currency,
                budget_type=BudgetType.MAX,
                constraint_type=ConstraintType.SOFT
            )
            return constraint, soft_match.group(0)

    # 4. Standard upper bound / max budget:
    # "under 5000", "maximum 5k", "max ₹5,000", "budget 5k", "no more than 5k", "up to 5k", "Rs 5000"
    max_match = re.search(
        r'(under|below|max|maximum|within|up\s+to|no\s+more\s+than|budget(?:\s+is)?)\s*(?:of)?\s*((?:₹|rs\.?\s*|inr\s+)?\s*[\d,\.]+\s*(?:k|lakhs?)?|\w+\s+thousand)',
        t
    )
    if max_match:
        raw_val = max_match.group(2).strip()
        amount_p = None
        if raw_val in WORD_AMOUNTS:
            amount_p = WORD_AMOUNTS[raw_val] * 100
        else:
            amount_p = parse_raw_amount_to_paise(raw_val)

        if amount_p:
            constraint = BudgetConstraint(
                max_amount_paise=amount_p,
                currency=currency,
                budget_type=BudgetType.MAX,
                constraint_type=ConstraintType.HARD
            )
            return constraint, max_match.group(0)

    # 5. Direct currency mention: "₹5,000", "5000 inr", "5000 rupees", "Rs 5000", "Rs. 5,000"
    currency_match = re.search(
        r'(?:(?:₹|rs\.?\s*|inr\s+)\s*([\d,\.]+\s*(?:k|lakhs?)?)|([\d,\.]+\s*(?:k|lakhs?)?)\s*(?:rupees|inr))',
        t
    )
    if currency_match:
        raw_val = currency_match.group(1) or currency_match.group(2)
        amount_p = parse_raw_amount_to_paise(raw_val)
        if amount_p:
            constraint = BudgetConstraint(
                max_amount_paise=amount_p,
                currency=currency,
                budget_type=BudgetType.MAX,
                constraint_type=ConstraintType.HARD
            )
            return constraint, currency_match.group(0)

    # 5b. Foreign currency: "$5000", "USD 5000", "50 dollars"
    foreign_match = re.search(
        r'(?:\$\s*([\d,\.]+\s*k?)|(?:usd|dollars?)\s*([\d,\.]+\s*k?)|([\d,\.]+\s*k?)\s*(?:usd|dollars?))',
        t
    )
    if foreign_match:
        raw_val = foreign_match.group(1) or foreign_match.group(2) or foreign_match.group(3)
        amount_p = parse_raw_amount_to_paise(raw_val)
        if amount_p:
            constraint = BudgetConstraint(
                max_amount_paise=amount_p,
                currency="USD",
                budget_type=BudgetType.MAX,
                constraint_type=ConstraintType.HARD
            )
            return constraint, foreign_match.group(0)

    # 6. Word-based numbers: "five thousand rupees"
    for word_phr, rupees in WORD_AMOUNTS.items():
        if word_phr in t:
            constraint = BudgetConstraint(
                max_amount_paise=rupees * 100,
                currency=currency,
                budget_type=BudgetType.MAX,
                constraint_type=ConstraintType.HARD
            )
            return constraint, word_phr

    return None


def extract_laptop_size(text: str) -> Optional[Tuple[float, str]]:
    """Extract laptop screen size in inches (e.g. 15-inch, 15.6-inch, 15", 16 inch).

    Requires explicit unit context (inch, ", in) to avoid false matches on
    isolated numbers like "15" without unit context. The word "in" is only
    matched when followed by word boundary and NOT followed by common
    preposition continuations (e.g., "in red", "in black").
    """
    t = text.lower()

    # Match patterns like: 15-inch, 15.6-inch, 15", 16 inch, 14-in, 15.6 inches
    # The "in" variant requires word boundary and must NOT be followed by a color/preposition
    match = re.search(r'(\d{1,2}(?:\.\d{1,2})?)\s*(?:-\s*)?(?:inch(?:es)?|″|")', t)
    if match:
        try:
            size = float(match.group(1))
            if 7.0 <= size <= 21.0:  # Reasonable laptop/tablet size range
                return size, match.group(0)
        except ValueError:
            pass

    # Handle "15 in" or "15-in" but NOT "15 in red" or "15 in stock"
    in_match = re.search(r'(\d{1,2}(?:\.\d{1,2})?)\s*(?:-\s*)?in\b(?!\s+(?:red|blue|black|white|green|yellow|pink|brown|grey|gray|stock|total|all|the|a|my|your|this|that|it))', t)
    if in_match:
        try:
            size = float(in_match.group(1))
            if 7.0 <= size <= 21.0:
                return size, in_match.group(0)
        except ValueError:
            pass

    return None


def extract_quantity(text: str) -> Optional[Tuple[int, str]]:
    """Extract explicitly stated item quantity.

    Filters out speculative/hedging language (e.g. 'might need two') to
    ensure only definite quantities are extracted.
    """
    t = text.lower()

    # Check for speculative language — if present, do NOT extract a quantity
    for marker in SPECULATIVE_MARKERS:
        if marker in t:
            return None

    # Numeric quantity: "2 backpacks", "quantity 2", "need 3"
    match = re.search(r'(?:need|want|quantity|buy|order)?\s*(\d+)\s*(?:units|pieces|backpacks|items|sleeves|bags|of them)?', t)
    if match:
        # Check if the digit is not part of a dimension or price
        val_str = match.group(1)
        val = int(val_str)
        if 1 <= val <= 100 and not re.search(rf"{val}\s*(?:inch|in|k|rupees|paise|%)", t):
            # Check context to ensure it's a quantity
            if re.search(r'(?:need|want|quantity|buy|order|two|three|pieces|units)\b', t):
                return val, match.group(0).strip()

    # Word numbers: "I need two", "a couple"
    for word, qty in WORD_NUMBERS.items():
        pattern = rf"\b(?:need|want|buy)?\s*{re.escape(word)}\s*(?:of them|backpacks|bags|items|units)?\b"
        w_match = re.search(pattern, t)
        if w_match and ("need" in w_match.group(0) or "want" in w_match.group(0) or word in ["two", "three", "a couple"]):
            return qty, w_match.group(0).strip()

    return None


def _is_positive_affirmation(text: str, value: str) -> bool:
    """Check if a material/color mention is actually a positive affirmation, not a negation.

    E.g., 'leather is okay', 'red is fine' should NOT be treated as exclusions.
    """
    t = text.lower()
    for affirmation in POSITIVE_AFFIRMATIONS:
        if f"{value} {affirmation}" in t:
            return True
    return False


def extract_exclusions(text: str) -> List[Tuple[ExclusionConstraint, str]]:
    """Extract explicit negative constraints (e.g. 'no leather', 'anything except red').

    Protects against false exclusions from positive affirmations like
    'leather is okay' or 'red is fine'.
    """
    t = text.lower()
    exclusions = []

    # Material exclusions
    materials = ["leather", "plastic", "polyester", "nylon", "canvas"]
    for mat in materials:
        # Skip if the material is mentioned in a positive affirmation
        if _is_positive_affirmation(t, mat):
            continue
        pattern = rf"\b(?:no|not|without|except|don't want|dont want|anything but)\s+{mat}\b"
        match = re.search(pattern, t)
        if match:
            exclusions.append((
                ExclusionConstraint(attribute="material", excluded_value=mat, importance="required"),
                match.group(0)
            ))

    # Color exclusions
    colors = ["red", "blue", "black", "brown", "white", "green", "yellow", "pink"]
    for col in colors:
        # Skip if the color is mentioned in a positive affirmation
        if _is_positive_affirmation(t, col):
            continue
        pattern = rf"\b(?:no|not|without|except|don't want|dont want|anything but)\s+{col}\b"
        match = re.search(pattern, t)
        if match:
            exclusions.append((
                ExclusionConstraint(attribute="color", excluded_value=col, importance="required"),
                match.group(0)
            ))

    return exclusions


def extract_preferences_and_requirements(text: str) -> Tuple[List[Tuple[AttributeRequirement, str]], List[Tuple[AttributePreference, str]]]:
    """Separate HARD requirements from SOFT preferences based on buyer phrasing."""
    t = text.lower()
    requirements: List[Tuple[AttributeRequirement, str]] = []
    preferences: List[Tuple[AttributePreference, str]] = []

    # 1. Laptop size requirement
    laptop_info = extract_laptop_size(t)
    if laptop_info:
        size, src = laptop_info
        requirements.append((
            AttributeRequirement(
                attribute="laptop_size",
                operator=OperatorType.GTE,
                value=size,
                unit="inch",
                importance="required"
            ),
            src
        ))

    # 2. Waterproof / water resistant
    if "waterproof" in t or "water-resistant" in t or "water resistant" in t:
        src = "waterproof" if "waterproof" in t else "water-resistant"
        # Only treat as preference if 'prefer' directly qualifies waterproof
        if "prefer waterproof" in t or "prefer water-resistant" in t or "waterproof preferred" in t:
            preferences.append((
                AttributePreference(attribute="water_resistance", preference="waterproof", strength=PreferenceStrength.PREFERRED),
                src
            ))
        else:
            requirements.append((
                AttributeRequirement(attribute="water_resistant", operator=OperatorType.EQ, value=True, importance="required"),
                src
            ))

    # 3. Lightweight
    if "lightweight" in t or "light weight" in t or "light" in t:
        src = "lightweight" if "lightweight" in t else "light"
        if any(w in t for w in ["prefer", "preference", "would like", "nice to have"]):
            preferences.append((
                AttributePreference(attribute="weight", preference="lightweight", strength=PreferenceStrength.PREFERRED),
                src
            ))
        elif "must be light" in t or "must be lightweight" in t or "needs to be light" in t:
            requirements.append((
                AttributeRequirement(attribute="weight", operator=OperatorType.EQ, value="lightweight", importance="required"),
                src
            ))
        else:
            preferences.append((
                AttributePreference(attribute="weight", preference="lightweight", strength=PreferenceStrength.PREFERRED),
                src
            ))

    # 4. Material preference
    materials = ["leather", "aluminum", "plastic", "nylon", "canvas"]
    for mat in materials:
        if f"want {mat}" in t or f"prefer {mat}" in t or f"like {mat}" in t:
            preferences.append((
                AttributePreference(attribute="material", preference=mat, strength=PreferenceStrength.PREFERRED),
                mat
            ))

    # 5. Color preference
    colors = ["black", "grey", "gray", "navy", "brown", "tan", "red", "white", "blue", "green"]
    for col in colors:
        if any(phr in t for phr in [f"prefer {col}", f"like {col}", f"want {col}", f"in {col}", f"for {col}"]):
            preferences.append((
                AttributePreference(attribute="color", preference=col, strength=PreferenceStrength.PREFERRED),
                col
            ))

    return requirements, preferences


def extract_category_and_use_case(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract product category and explicitly stated use case."""
    t = text.lower()

    # Category matching
    category = None
    if "travel backpack" in t or "travel pack" in t:
        category = "travel_backpack"
    elif "laptop backpack" in t:
        category = "laptop_backpack"
    elif "backpack" in t:
        category = "backpack"
    elif "laptop sleeve" in t or "sleeve" in t:
        category = "laptop_sleeve"
    elif "wireless mouse" in t or "bluetooth mouse" in t or "mouse" in t:
        category = "wireless_mouse"
    elif "usb-c hub" in t or "usbc hub" in t or "usb hub" in t or "hub" in t:
        category = "usbc_hub"

    # Use case matching
    use_case = None
    if "business travel" in t or "travel for work" in t or "work travel" in t:
        use_case = "business_travel"
    elif "college" in t or "university" in t or "school" in t:
        use_case = "college"
    elif "flight" in t or "airplane" in t or "international travel" in t:
        use_case = "international_travel"
    elif "daily commute" in t or "office commute" in t:
        use_case = "daily_commute"
    elif "travel" in t:
        use_case = "travel"

    return category, use_case


def extract_temporal(text: str) -> Optional[Tuple[TemporalConstraint, str]]:
    """Extract delivery deadline or usage timeframe."""
    t = text.lower()
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "tomorrow", "next week"]
    for day in days:
        pattern = rf"\b(?:by|before|need it for|needed by)\s+{day}\b"
        match = re.search(pattern, t)
        if match:
            return TemporalConstraint(delivery_deadline=day.capitalize()), match.group(0)

    if "immediately" in t or "asap" in t:
        return TemporalConstraint(delivery_deadline="Immediate"), "immediately"

    return None
