"""Buyer Context Key Builder: Derives deterministic, non-PII commercial intent context keys.

Core Invariant: Zero demographic profiling, zero personal identity, zero customer surveillance.
"""

import hashlib
from typing import Dict, Any, List
from domain.intent_schemas import BuyerIntent
from services.learning.schemas import BuyerContextDimensions
from services.learning.errors import SecurityBoundaryError


FORBIDDEN_DEMOGRAPHIC_KEYS = {
    "age", "gender", "sex", "race", "ethnicity", "religion",
    "income", "salary", "net_worth", "credit_score", "zipcode",
    "postal_code", "location", "address", "phone", "email",
    "name", "user_id", "shopper_id", "political", "health", "medical"
}


class BuyerContextKeyBuilder:
    """Constructs deterministic, privacy-preserving commercial intent context keys."""

    @staticmethod
    def get_budget_tier(max_amount_paise: int) -> str:
        """Map integer paise budget into standardized commercial budget tiers."""
        if max_amount_paise <= 200000:
            return "TIER_ENTRY_LE2K"
        elif max_amount_paise <= 400000:
            return "TIER_MID_2K_4K"
        elif max_amount_paise <= 600000:
            return "TIER_PRO_4K_6K"
        else:
            return "TIER_PREMIUM_GT6K"

    @classmethod
    def validate_zero_demographics(cls, intent: BuyerIntent) -> None:
        """Strictly verify that BuyerIntent contains zero demographic or personal profiling data."""
        # Check requirements attributes
        for req in intent.requirements:
            if req.attribute.lower() in FORBIDDEN_DEMOGRAPHIC_KEYS:
                raise SecurityBoundaryError(
                    f"Forbidden demographic attribute '{req.attribute}' detected. "
                    "Buyer context keys strictly prohibit demographic profiling."
                )

        # Check preferences attributes
        for pref in intent.preferences:
            if pref.attribute.lower() in FORBIDDEN_DEMOGRAPHIC_KEYS:
                raise SecurityBoundaryError(
                    f"Forbidden demographic attribute '{pref.attribute}' detected in preferences."
                )

        # Check exclusions attributes
        for excl in intent.exclusions:
            if excl.attribute.lower() in FORBIDDEN_DEMOGRAPHIC_KEYS:
                raise SecurityBoundaryError(
                    f"Forbidden demographic attribute '{excl.attribute}' detected in exclusions."
                )

    @classmethod
    def extract_dimensions(
        cls,
        intent: BuyerIntent,
        category: str = "travel_backpack"
    ) -> BuyerContextDimensions:
        """Extract structured, normalized non-demographic commercial dimensions."""
        cls.validate_zero_demographics(intent)

        # 1. Budget Tier
        b_paise = None
        if intent.budget:
            b_paise = intent.budget.max_amount_paise if intent.budget.max_amount_paise is not None else intent.budget.amount_paise
        budget_paise = b_paise if b_paise is not None else 400000
        budget_tier = cls.get_budget_tier(budget_paise)

        # 2. Hard Requirements Signature (Sorted & Normalized)
        req_parts = []
        for req in sorted(intent.requirements, key=lambda r: r.attribute):
            op = req.operator.value if hasattr(req.operator, "value") else str(req.operator)
            val = str(req.value).lower()
            req_parts.append(f"{req.attribute.lower()}:{op}:{val}")
        hard_sig = "|".join(req_parts) if req_parts else "none"

        # 3. Soft Preferences Signature (Sorted & Normalized)
        pref_parts = []
        for pref in sorted(intent.preferences, key=lambda p: p.attribute):
            val = str(pref.preference).lower()
            pref_parts.append(f"{pref.attribute.lower()}:{val}")
        pref_sig = "|".join(pref_parts) if pref_parts else "none"

        # 4. Exclusions Signature (Sorted & Normalized)
        excl_parts = []
        for excl in sorted(intent.exclusions, key=lambda e: e.attribute):
            val = str(excl.excluded_value).lower()
            excl_parts.append(f"{excl.attribute.lower()}:{val}")
        excl_sig = "|".join(excl_parts) if excl_parts else "none"

        cat_str = category if category is not None else "travel_backpack"
        return BuyerContextDimensions(
            category=cat_str.lower(),
            budget_tier=budget_tier,
            hard_requirement_signature=hard_sig,
            preference_signature=pref_sig,
            exclusion_signature=excl_sig
        )

    @classmethod
    def build_key(
        cls,
        intent: BuyerIntent,
        category: str = "travel_backpack"
    ) -> str:
        """Generate deterministic, non-demographic buyer context key (e.g. bck_travel_backpack_mid_...)."""
        dims = cls.extract_dimensions(intent, category)

        raw_signature = (
            f"cat={dims.category};"
            f"tier={dims.budget_tier};"
            f"reqs={dims.hard_requirement_signature};"
            f"prefs={dims.preference_signature};"
            f"excls={dims.exclusion_signature}"
        )
        digest = hashlib.sha256(raw_signature.encode("utf-8")).hexdigest()[:12]
        return f"bck_{dims.category}_{dims.budget_tier}_{digest}"
