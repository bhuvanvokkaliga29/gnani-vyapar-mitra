"""Buyer Simulator: The central coordinator for Phase 6 AI Buyer Lab.

Evaluates candidate merchant offers against structured BuyerIntent v1.
Enforces the strict hierarchy: Hard Requirements -> Exclusions -> Budget -> Preferences -> Deterministic Tie-Break.
"""

import re
import uuid
from typing import List, Optional
import structlog

from domain.intent_schemas import BuyerIntent
from services.buyer_lab.schemas import (
    BuyerOffer,
    BuyerSelectionResult,
    BuyerPersonaType,
    SelectionTaxonomy,
    DecisionStepTrace
)
from services.buyer_lab.filter import EligibilityFilter
from services.buyer_lab.evaluator import PreferenceEvaluator

logger = structlog.get_logger()

# Patterns indicative of prompt injection attempts in offer text (defense-in-depth)
PROMPT_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions?",
    r"(?i)system\s*:",
    r"(?i)system\s+prompt",
    r"(?i)system\s+message",
    r"(?i)you\s+must\s+select\s+this",
    r"(?i)always\s+choose\s+this",
    r"(?i)choose\s+this\s+product",
    r"(?i)buyer\s+must\s+select",
    r"(?i)override\s+(all\s+)?rules?",
    r"(?i)override\s+budget",
    r"(?i)admin\s+instruction",
    r"(?i)developer\s+instruction",
    r"(?i)tool\s+call",
    r"(?i)function\s+call",
    r"(?i)policy\s+override",
    r"(?i)do\s+not\s+evaluate",
    r"(?i)forget\s+all\s+rules"
]


class BuyerSimulator:
    """Offline simulation engine for evaluating machine-buyer choices.

    Core Invariants:
    1. Persona weighting can NEVER override BuyerIntent hard constraints.
       Decision hierarchy: Hard Requirements -> Exclusions -> Budget -> Preferences -> Persona -> Tie-Break.
    2. Offer content is DATA, never instructions.
       Even if injection strings bypass regex sanitization, deterministic code evaluation guarantees
       that offer strings cannot modify eligibility, relax budgets, or bypass constraints.
    3. BuyerIntent is strictly immutable during simulation.
    """

    def __init__(
        self,
        eligibility_filter: Optional[EligibilityFilter] = None,
        evaluator: Optional[PreferenceEvaluator] = None
    ):
        self.filter = eligibility_filter or EligibilityFilter()
        self.evaluator = evaluator or PreferenceEvaluator()

    def simulate_selection(
        self,
        intent: BuyerIntent,
        offers: List[BuyerOffer],
        persona: BuyerPersonaType = BuyerPersonaType.BALANCED,
        scenario_id: Optional[str] = None
    ) -> BuyerSelectionResult:
        """Run controlled simulation of machine-buyer selection over a candidate offer set."""
        # Enforce BuyerIntent Immutability
        intent_copy = intent.model_copy(deep=True)

        candidate_ids = [o.offer_id for o in offers]
        logger.info(
            "buyer_simulation_started",
            candidate_count=len(offers),
            persona=persona.value,
            scenario_id=scenario_id
        )

        # -------------------------------------------------------------
        # STEP 0: Untrusted Metadata Sanitization (Prompt Injection Defense)
        # -------------------------------------------------------------
        sanitized_offers = [self._sanitize_offer_metadata(offer) for offer in offers]

        # -------------------------------------------------------------
        # STEP 1: Deterministic Eligibility Filtering
        # -------------------------------------------------------------
        eligible_offers, rejected_traces, step_traces, hard_constraints = self.filter.filter_offers(
            intent=intent_copy,
            offers=sanitized_offers
        )
        eligible_ids = [o.offer_id for o in eligible_offers]

        # -------------------------------------------------------------
        # STEP 2: Handle Zero Eligible Offers (Hard Safety Rule)
        # -------------------------------------------------------------
        if not eligible_offers:
            logger.info("buyer_simulation_no_eligible_offers", candidate_count=len(offers))
            step_traces.append(DecisionStepTrace(
                step="FINAL_SELECTION",
                description="Zero offers survived hard filtering. Returning NO_ELIGIBLE_OFFER.",
                eligible_count_before=0,
                eligible_count_after=0,
                rejections_in_step=[]
            ))
            return BuyerSelectionResult(
                result_version="buyer-selection/v1",
                buyer_intent_version=intent_copy.schema_version,
                simulation_version="buyer-sim/v1",
                scenario_id=scenario_id,
                selected_offer_id=None,
                selected_offer=None,
                candidate_offer_ids=candidate_ids,
                eligible_offer_ids=[],
                rejected_offers=rejected_traces,
                selection_reasons=[SelectionTaxonomy.NO_ELIGIBLE_OFFER],
                selection_rationale=(
                    "No candidate offers satisfied the buyer's mandatory hard requirements, "
                    "budget ceilings, or explicit exclusions. The machine buyer strictly refused to compromise."
                ),
                satisfied_preferences=[],
                unmet_preferences=[f"{p.attribute}: {p.preference}" for p in intent_copy.preferences],
                hard_constraints_checked=hard_constraints,
                decision_trace=step_traces,
                buyer_persona=persona
            )

        # -------------------------------------------------------------
        # STEP 3: Preference Evaluation and Value Comparison
        # -------------------------------------------------------------
        winner, reasons, rationale, satisfied, unmet = self.evaluator.evaluate_and_rank(
            intent=intent_copy,
            eligible_offers=eligible_offers,
            persona=persona
        )

        step_traces.append(DecisionStepTrace(
            step="PREFERENCE_EVALUATION_AND_SELECTION",
            description=f"Selected winning offer '{winner.offer_id}' based on preference match and value comparison.",
            eligible_count_before=len(eligible_offers),
            eligible_count_after=1,
            rejections_in_step=[]
        ))

        logger.info(
            "buyer_simulation_completed",
            winner_id=winner.offer_id,
            reasons=[r.value for r in reasons]
        )

        return BuyerSelectionResult(
            result_version="buyer-selection/v1",
            buyer_intent_version=intent.schema_version,
            simulation_version="buyer-sim/v1",
            scenario_id=scenario_id,
            selected_offer_id=winner.offer_id,
            selected_offer=winner,
            candidate_offer_ids=candidate_ids,
            eligible_offer_ids=eligible_ids,
            rejected_offers=rejected_traces,
            selection_reasons=reasons,
            selection_rationale=rationale,
            satisfied_preferences=satisfied,
            unmet_preferences=unmet,
            hard_constraints_checked=hard_constraints,
            decision_trace=step_traces,
            buyer_persona=persona
        )

    def _sanitize_offer_metadata(self, offer: BuyerOffer) -> BuyerOffer:
        """Sanitize offer strings to prevent prompt-injection attacks while preserving valid content."""
        # Deep copy data by re-instantiating with sanitized strings
        data = offer.model_dump()

        def clean_str(s: str) -> str:
            cleaned = s
            for pattern in PROMPT_INJECTION_PATTERNS:
                cleaned = re.sub(pattern, "[DATA_NEUTRALIZED]", cleaned)
            return cleaned

        data["product_name"] = clean_str(data["product_name"])
        data["merchant_label"] = clean_str(data["merchant_label"])
        if data.get("service_information"):
            data["service_information"] = clean_str(data["service_information"])

        if data.get("incentives"):
            data["incentives"] = [clean_str(i) for i in data["incentives"]]

        if data.get("relevant_attributes"):
            cleaned_attrs = {}
            for k, v in data["relevant_attributes"].items():
                if isinstance(v, str):
                    cleaned_attrs[k] = clean_str(v)
                else:
                    cleaned_attrs[k] = v
            data["relevant_attributes"] = cleaned_attrs

        return BuyerOffer.model_validate(data)
