"""Feature representation contract and deterministic extractor for Phase 8.4.

Contract Version: feature-schema/v1
Dimensions: 19
"""

from typing import Optional, Dict, Any, List
import math
from domain.intent_schemas import BuyerIntent
from services.policy.schemas import PolicyCandidate, CandidateEconomics, StrategyType
from services.learning.model_errors import IncompatibleFeatureSchemaError

FEATURE_SCHEMA_VERSION = "feature-schema/v1"
FEATURE_DIMENSION = 19

FEATURE_NAMES: List[str] = [
    "bias",
    "budget_tier_norm",
    "budget_amount_norm",
    "is_bulk_quantity",
    "has_explicit_pref",
    "has_hard_reqs",
    "is_single_product",
    "is_comp_bundle",
    "is_value_bundle",
    "is_alt_product",
    "is_bounded_discount",
    "is_non_price_inc",
    "discount_norm",
    "product_count_norm",
    "baseline_price_norm",
    "budget_x_discount",
    "pref_x_bundle",
    "budget_x_bundle",
    "price_x_discount"
]


class PolicyFeatureExtractor:
    """Extracts a deterministic 19-dimensional feature vector from pre-decision intent and candidate policy."""

    @classmethod
    def extract(
        cls,
        intent: Optional[BuyerIntent] = None,
        candidate: Optional[PolicyCandidate] = None,
        economics: Optional[CandidateEconomics] = None,
        buyer_context_key: Optional[str] = None,
        candidate_snapshot: Optional[Dict[str, Any]] = None
    ) -> List[float]:
        """Extract a 19-dimensional feature vector.
        
        Strict Invariants:
        1. Pre-decision information ONLY. Zero post-outcome leakage.
        2. Exactly 19 dimensions.
        3. All values are finite float.
        4. Deterministic: identical inputs produce identical vectors.
        """
        features = [0.0] * FEATURE_DIMENSION

        # 0. Intercept / Bias
        features[0] = 1.0

        # --- A. Buyer / Context Features (Indices 1 to 5) ---
        budget_tier_val = 0.50
        budget_amount_val = 0.50
        is_bulk_val = 0.0
        has_pref_val = 0.0
        has_hard_val = 0.0

        if intent is not None:
            # 1. Budget Tier
            tier_str = buyer_context_key.upper() if buyer_context_key else ""

            # 2. Budget Amount Normalized (capped at ₹10,000 = 1,000,000 paise)
            if intent.budget and intent.budget.max_amount_paise:
                budget_amount_val = float(min(intent.budget.max_amount_paise, 1000000)) / 1000000.0
            elif intent.budget and intent.budget.amount_paise:
                budget_amount_val = float(min(intent.budget.amount_paise, 1000000)) / 1000000.0
            
            # Map budget amount to tier if tier string not explicit
            if budget_amount_val < 0.35:
                budget_tier_val = 0.25
            elif budget_amount_val < 0.65:
                budget_tier_val = 0.50
            elif budget_amount_val < 0.85:
                budget_tier_val = 0.75
            else:
                budget_tier_val = 1.00

            # 3. Quantity
            is_bulk_val = 1.0 if (intent.quantity and intent.quantity > 1) else 0.0

            # 4. Explicit Preferences
            has_pref_val = 1.0 if (intent.preferences and len(intent.preferences) > 0) else 0.0

            # 5. Hard Requirements
            has_hard_val = 1.0 if (intent.requirements and len(intent.requirements) > 0) else 0.0

        elif buyer_context_key:
            # Fallback extraction from context key (e.g. bck_backpack_tier_mid_...)
            key_upper = buyer_context_key.upper()
            if "LOW" in key_upper:
                budget_tier_val = 0.25
            elif "MID" in key_upper:
                budget_tier_val = 0.50
            elif "HIGH" in key_upper:
                budget_tier_val = 0.75
            elif "PREMIUM" in key_upper:
                budget_tier_val = 1.00
            budget_amount_val = budget_tier_val

        features[1] = budget_tier_val
        features[2] = budget_amount_val
        features[3] = is_bulk_val
        features[4] = has_pref_val
        features[5] = has_hard_val

        # --- B. Candidate Policy Features (Indices 6 to 14) ---
        strategy_str = "SINGLE_PRODUCT"
        discount_val = 0.0
        product_count_val = 0.20
        baseline_price_val = 0.35

        # Unpack candidate from object or snapshot
        cand_dict: Dict[str, Any] = {}
        if candidate is not None:
            cand_dict = candidate.model_dump()
        elif candidate_snapshot is not None:
            cand_dict = candidate_snapshot

        if cand_dict:
            strategy_str = str(cand_dict.get("strategy_type", "SINGLE_PRODUCT"))
            incentive = cand_dict.get("incentive") or {}
            if isinstance(incentive, dict):
                disc_pct = incentive.get("discount_percent")
                if disc_pct is not None:
                    discount_val = float(disc_pct) / 100.0
            
            p_ids = cand_dict.get("product_ids") or []
            bundle_comps = cand_dict.get("bundle_components") or []
            total_items = max(len(p_ids), len(bundle_comps), 1)
            product_count_val = float(min(total_items, 5)) / 5.0

        # Unpack economics
        if economics is not None:
            baseline_price_val = float(min(economics.gross_revenue_paise, 1000000)) / 1000000.0
            if economics.effective_discount_percent:
                discount_val = float(economics.effective_discount_percent) / 100.0

        # One-hot Strategy Types
        features[6] = 1.0 if "SINGLE_PRODUCT" in strategy_str else 0.0
        features[7] = 1.0 if "COMPLEMENTARY_BUNDLE" in strategy_str else 0.0
        features[8] = 1.0 if "VALUE_BUNDLE" in strategy_str else 0.0
        features[9] = 1.0 if "ALTERNATIVE_PRODUCT" in strategy_str else 0.0
        features[10] = 1.0 if "BOUNDED_DISCOUNT" in strategy_str else 0.0
        features[11] = 1.0 if "NON_PRICE_INCENTIVE" in strategy_str else 0.0

        features[12] = discount_val
        features[13] = product_count_val
        features[14] = baseline_price_val

        # --- C. Interaction Features (Indices 15 to 18) ---
        is_bundle = features[7] + features[8]  # COMPLEMENTARY or VALUE bundle
        features[15] = features[1] * features[12]   # budget_tier * discount
        features[16] = features[4] * is_bundle      # preference * bundle
        features[17] = features[1] * is_bundle      # budget_tier * bundle
        features[18] = features[14] * features[12]  # baseline_price * discount

        # Validation checks
        if any(math.isnan(v) or math.isinf(v) for v in features):
            raise IncompatibleFeatureSchemaError("Extracted feature vector contains NaN or infinite values.")

        if len(features) != FEATURE_DIMENSION:
            raise IncompatibleFeatureSchemaError(
                f"Feature vector dimension {len(features)} != expected ({FEATURE_DIMENSION})"
            )

        return features
