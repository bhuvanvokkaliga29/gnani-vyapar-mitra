"""Transparent Multi-Factor Policy Scoring & Ranking Engine.

Calculates grounded composite scores without fake conversion probabilities.
Ranks candidate strategies according to active merchant commercial objectives.
"""

from decimal import Decimal
from typing import List, Dict, Any, Optional
from domain.commerce_schemas import MerchantCommerceContext, ProductResponse
from domain.intent_schemas import BuyerIntent
from services.policy.schemas import (
    PolicyCandidate,
    PolicyScore,
    CandidateValidationStatus,
    StrategyType
)

# Objective-specific weighting profiles
OBJECTIVE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "BALANCE_REVENUE_AND_MARGIN": {
        "buyer_fit": 0.35,
        "economic_value": 0.25,
        "objective_alignment": 0.20,
        "constraint_safety": 0.20
    },
    "MAXIMIZE_REVENUE": {
        "buyer_fit": 0.30,
        "economic_value": 0.40,
        "objective_alignment": 0.20,
        "constraint_safety": 0.10
    },
    "MAXIMIZE_CONTRIBUTION": {
        "buyer_fit": 0.30,
        "economic_value": 0.40,
        "objective_alignment": 0.20,
        "constraint_safety": 0.10
    },
    "INCREASE_AOV": {
        "buyer_fit": 0.25,
        "economic_value": 0.35,
        "objective_alignment": 0.30,
        "constraint_safety": 0.10
    }
}


class PolicyScorer:
    """Computes transparent, explainable scoring components for candidate strategies."""

    def score_candidate(
        self,
        candidate: PolicyCandidate,
        intent: BuyerIntent,
        context: MerchantCommerceContext
    ) -> PolicyCandidate:
        """Calculate multi-factor scores and attach PolicyScore to candidate."""
        # Rejected or NO_OFFER candidates get zero scores
        if candidate.validation_status != CandidateValidationStatus.APPROVED or candidate.strategy_type == StrategyType.NO_OFFER:
            candidate.score = PolicyScore(
                buyer_fit_score=0.0,
                economic_value_score=0.0,
                objective_alignment_score=0.0,
                constraint_safety_score=0.0,
                composite_score=0.0
            )
            return candidate

        prod_map: Dict[str, ProductResponse] = {p.id: p for p in context.products}
        primary_prod = prod_map.get(candidate.product_ids[0]) if candidate.product_ids else None

        # 1. Buyer Fit Score (0.0 - 1.0)
        fit_score = 0.60  # Baseline for passing validation & category match
        if primary_prod:
            attrs = primary_prod.attributes or {}
            # Preference matching
            for pref in intent.preferences:
                prod_attr = str(attrs.get(pref.attribute, "")).lower()
                if pref.preference.lower() in prod_attr or prod_attr in pref.preference.lower():
                    fit_score += 0.10
            # Use-case matching
            if intent.use_case and primary_prod.description:
                if intent.use_case.replace("_", " ").lower() in primary_prod.description.lower():
                    fit_score += 0.10
        buyer_fit = min(1.0, fit_score)

        # 2. Economic Value Score (0.0 - 1.0)
        target_aov = context.constraints.get("target_aov_paise", 400000)
        econ = candidate.deterministic_economics
        if econ and target_aov > 0:
            # Score contribution toward or above target AOV
            economic_value = min(1.0, econ.net_revenue_paise / float(target_aov))
        else:
            economic_value = 0.5

        # 3. Objective Alignment Score (0.0 - 1.0)
        obj = context.business_objective
        margin_floor = float(context.constraints.get("minimum_margin_percent", 25.0))

        if obj == "MAXIMIZE_REVENUE":
            # Higher net revenue within budget scores higher
            max_budget = float(intent.budget.max_amount_paise) if intent.budget and intent.budget.max_amount_paise else float(target_aov * 2)
            alignment = min(1.0, econ.net_revenue_paise / max_budget) if econ else 0.5

        elif obj == "MAXIMIZE_CONTRIBUTION":
            # Higher absolute gross profit scores higher
            expected_profit = target_aov * 0.40  # 40% target profit baseline
            alignment = min(1.0, econ.gross_profit_paise / expected_profit) if econ else 0.5

        elif obj == "INCREASE_AOV":
            # Multi-product bundles score highest
            if len(candidate.product_ids) > 1:
                alignment = min(1.0, 0.70 + 0.30 * min(1.0, econ.net_revenue_paise / float(target_aov))) if econ else 0.7
            else:
                alignment = min(0.60, econ.net_revenue_paise / float(target_aov)) if econ else 0.4

        else:  # BALANCE_REVENUE_AND_MARGIN
            # Rewards healthy margin buffer above floor + solid revenue
            if econ:
                margin_buffer = max(0.0, float(econ.gross_margin_percent) - margin_floor) / 50.0
                margin_factor = min(1.0, margin_buffer)
                rev_factor = min(1.0, econ.net_revenue_paise / float(target_aov))
                alignment = 0.5 * margin_factor + 0.5 * rev_factor
            else:
                alignment = 0.5

        alignment = round(min(1.0, max(0.0, alignment)), 3)

        # 4. Constraint Safety Score (0.0 - 1.0)
        safety = 0.80  # Baseline for strictly approved candidates
        if econ:
            # Reward extra margin buffer above floor
            current_margin = float(econ.gross_margin_percent)
            if current_margin > margin_floor + 5.0:
                safety += 0.10
            if current_margin > margin_floor + 15.0:
                safety += 0.10
        constraint_safety = min(1.0, safety)

        # 5. Composite Score
        weights = OBJECTIVE_WEIGHTS.get(obj, OBJECTIVE_WEIGHTS["BALANCE_REVENUE_AND_MARGIN"])
        composite = (
            weights["buyer_fit"] * buyer_fit +
            weights["economic_value"] * economic_value +
            weights["objective_alignment"] * alignment +
            weights["constraint_safety"] * constraint_safety
        )
        composite = round(min(1.0, max(0.0, composite)), 3)

        candidate.score = PolicyScore(
            buyer_fit_score=round(buyer_fit, 3),
            economic_value_score=round(economic_value, 3),
            objective_alignment_score=alignment,
            constraint_safety_score=round(constraint_safety, 3),
            composite_score=composite
        )
        return candidate

    def rank_candidates(
        self,
        candidates: List[PolicyCandidate],
        context: MerchantCommerceContext
    ) -> List[PolicyCandidate]:
        """Sort candidates: APPROVED first (descending by composite score), then REJECTED."""
        approved = [c for c in candidates if c.validation_status == CandidateValidationStatus.APPROVED]
        rejected = [c for c in candidates if c.validation_status != CandidateValidationStatus.APPROVED]

        # Sort approved by composite_score descending
        approved.sort(
            key=lambda c: (c.score.composite_score if c.score else 0.0),
            reverse=True
        )

        return approved + rejected
