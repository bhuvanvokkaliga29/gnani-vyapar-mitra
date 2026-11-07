"""Preference Evaluator and Deterministic Tie-Breaker for AI Buyer Lab.

Evaluates eligible offers against soft buyer preferences and buyer-visible value dimensions.
Applies deterministic tie-breaking without random chance or merchant favoritism.
"""

from typing import List, Tuple, Dict, Any, Optional
from decimal import Decimal
import structlog

from domain.intent_schemas import BuyerIntent, PreferenceStrength
from services.buyer_lab.schemas import (
    BuyerOffer,
    SelectionTaxonomy,
    BuyerPersonaType
)

logger = structlog.get_logger()


class PreferenceEvaluator:
    """Evaluates eligible offers on buyer-visible value and soft preferences."""

    def evaluate_and_rank(
        self,
        intent: BuyerIntent,
        eligible_offers: List[BuyerOffer],
        persona: BuyerPersonaType = BuyerPersonaType.BALANCED
    ) -> Tuple[BuyerOffer, List[SelectionTaxonomy], str, List[str], List[str]]:
        """Rank eligible offers and select the winning offer.

        Returns:
            (winning_offer, selection_reasons, selection_rationale, satisfied_prefs, unmet_prefs)
        """
        if not eligible_offers:
            raise ValueError("evaluate_and_rank requires at least one eligible offer")

        if len(eligible_offers) == 1:
            winner = eligible_offers[0]
            reasons = [SelectionTaxonomy.HARD_REQUIREMENT_MATCH]
            if intent.budget:
                reasons.append(SelectionTaxonomy.BUDGET_MATCH)
            satisfied, unmet = self._evaluate_preferences(intent, winner)
            if satisfied:
                reasons.append(SelectionTaxonomy.PREFERENCE_MATCH)
            rationale = (
                f"Offer '{winner.offer_id}' from {winner.merchant_label} was the sole eligible offer satisfying "
                f"all hard requirements and budget constraints at ₹{winner.price_paise / 100:.2f}."
            )
            return winner, reasons, rationale, satisfied, unmet

        # Multi-offer competition
        max_budget = None
        if intent.budget:
            max_budget = intent.budget.max_amount_paise or intent.budget.amount_paise

        # Compute candidate utility tuples: (score, preference_matches, -price_paise, -offer_id)
        scored_candidates = []
        for offer in eligible_offers:
            satisfied, unmet = self._evaluate_preferences(intent, offer)
            score = self._compute_offer_score(intent, offer, satisfied, max_budget, persona)
            # Tie-break tuple:
            # 1. Higher total composite utility score
            # 2. More satisfied preferences
            # 3. Lower price in paise (represented as negative price so max works)
            # 4. Deterministic alphabetical offer_id (reversed so 'a' beats 'z' in max)
            scored_candidates.append({
                "offer": offer,
                "score": score,
                "satisfied": satisfied,
                "unmet": unmet,
                "pref_count": len(satisfied),
                "price": offer.price_paise,
                "offer_id": offer.offer_id
            })

        # Sort using deterministic tie-break hierarchy:
        # We sort by:
        # (-score, -pref_count, price, offer_id)
        # and take index 0.
        scored_candidates.sort(key=lambda c: (
            -round(c["score"], 4),
            -c["pref_count"],
            c["price"],
            c["offer_id"]
        ))

        best = scored_candidates[0]
        winner = best["offer"]
        satisfied = best["satisfied"]
        unmet = best["unmet"]

        # Determine Selection Taxonomy
        reasons: List[SelectionTaxonomy] = [SelectionTaxonomy.HARD_REQUIREMENT_MATCH]
        if intent.budget:
            reasons.append(SelectionTaxonomy.BUDGET_MATCH)

        if satisfied:
            reasons.append(SelectionTaxonomy.PREFERENCE_MATCH)

        # Check if lowest price among eligible
        min_eligible_price = min(o.price_paise for o in eligible_offers)
        if winner.price_paise == min_eligible_price:
            reasons.append(SelectionTaxonomy.LOWER_PRICE_AMONG_ELIGIBLE)

        # Feature specific bonuses
        if winner.included_items:
            reasons.append(SelectionTaxonomy.BUNDLE_VALUE)
        if winner.warranty_months > 12:
            reasons.append(SelectionTaxonomy.WARRANTY_VALUE)
        if winner.delivery_days <= 2:
            reasons.append(SelectionTaxonomy.DELIVERY_VALUE)

        # Check if tie-breaking was required between top 2
        if len(scored_candidates) > 1:
            runner_up = scored_candidates[1]
            if round(best["score"], 4) == round(runner_up["score"], 4):
                reasons.append(SelectionTaxonomy.DETERMINISTIC_TIE_BREAK)

        # Grounded Rationale
        rationale_parts = [
            f"Offer '{winner.offer_id}' ({winner.product_name}) from {winner.merchant_label} selected among "
            f"{len(eligible_offers)} eligible offers."
        ]
        rationale_parts.append(f"Offered at ₹{winner.price_paise / 100:.2f}.")
        if satisfied:
            rationale_parts.append(f"Satisfies {len(satisfied)} preferences ({', '.join(satisfied)}).")
        if winner.warranty_months > 12:
            rationale_parts.append(f"Includes extended {winner.warranty_months}-month warranty.")
        if winner.included_items:
            rationale_parts.append(f"Includes bundle items: {', '.join(winner.included_items)}.")
        if winner.price_paise == min_eligible_price and len(eligible_offers) > 1:
            rationale_parts.append("Provided the lowest price among all compliant offers.")

        rationale = " ".join(rationale_parts)
        return winner, reasons, rationale, satisfied, unmet

    def _evaluate_preferences(
        self,
        intent: BuyerIntent,
        offer: BuyerOffer
    ) -> Tuple[List[str], List[str]]:
        """Evaluate which soft preferences are satisfied or unmet by an offer."""
        satisfied: List[str] = []
        unmet: List[str] = []

        for pref in intent.preferences:
            attr = pref.attribute.strip().lower()
            desired = pref.preference.strip().lower()
            match = False

            # 1. Warranty preference
            if "warranty" in attr or "warranty" in desired:
                if offer.warranty_months >= 24:
                    match = True
                elif "long" in desired and offer.warranty_months > 12:
                    match = True

            # 2. Delivery / speed preference
            elif "delivery" in attr or "speed" in attr or "fast" in desired:
                if offer.delivery_days <= 2:
                    match = True

            # 3. Weight preference (e.g. lightweight)
            elif "weight" in attr or "light" in desired:
                weight = offer.relevant_attributes.get("weight_kg")
                if weight is not None and float(weight) <= 1.2:
                    match = True

            # 4. Color / Material in attributes or product name
            elif attr in offer.relevant_attributes:
                val = str(offer.relevant_attributes[attr]).lower()
                if desired in val:
                    match = True

            # 5. Bundle preference
            elif "bundle" in attr or "accessory" in attr or "accessories" in desired:
                if len(offer.included_items) > 0:
                    match = True

            # 6. Fallback string search across product_name and incentives
            elif desired in offer.product_name.lower():
                match = True
            elif any(desired in inc.lower() for inc in offer.incentives):
                match = True

            if match:
                satisfied.append(f"{pref.attribute}: {pref.preference}")
            else:
                unmet.append(f"{pref.attribute}: {pref.preference}")

        return satisfied, unmet

    def _compute_offer_score(
        self,
        intent: BuyerIntent,
        offer: BuyerOffer,
        satisfied_prefs: List[str],
        max_budget: Optional[int],
        persona: BuyerPersonaType
    ) -> float:
        """Compute observable value score based on preferences, price efficiency, and persona weights."""
        base_score = 50.0

        # Preference satisfaction component (0 to 30 points)
        total_prefs = len(intent.preferences)
        if total_prefs > 0:
            pref_ratio = len(satisfied_prefs) / total_prefs
            base_score += pref_ratio * 30.0

        # Price efficiency component (0 to 20 points)
        if max_budget and max_budget > 0:
            savings_ratio = max(0.0, float(max_budget - offer.price_paise) / float(max_budget))
            price_score = min(20.0, savings_ratio * 20.0)
        else:
            price_score = 10.0

        # Persona weights adjustment
        if persona == BuyerPersonaType.PRICE_SENSITIVE:
            score = (base_score * 0.7) + (price_score * 2.0)
        elif persona == BuyerPersonaType.WARRANTY_SERVICE:
            warranty_pts = min(15.0, (offer.warranty_months / 12.0) * 5.0)
            score = base_score + price_score + warranty_pts
        elif persona == BuyerPersonaType.BUNDLE_VALUE:
            bundle_pts = min(15.0, len(offer.included_items) * 5.0)
            score = base_score + price_score + bundle_pts
        elif persona == BuyerPersonaType.FEATURE_PRIORITY:
            score = (base_score * 1.3) + (price_score * 0.5)
        else:
            # BALANCED
            score = base_score + price_score

        # Add modest bonuses for buyer-visible perks
        if offer.warranty_months > 12:
            score += 3.0
        if offer.delivery_days <= 2:
            score += 2.0
        if len(offer.included_items) > 0:
            score += 2.5
        if "free_shipping" in [inc.lower() for inc in offer.incentives]:
            score += 1.5

        return float(score)
