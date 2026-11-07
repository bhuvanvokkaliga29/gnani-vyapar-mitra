"""Hybrid Deterministic & Structured Intent Extractor Engine."""

import re
import structlog
from typing import Optional, List, Dict, Any, Tuple
from domain.intent_schemas import (
    BuyerIntent,
    BudgetConstraint,
    AttributeRequirement,
    AttributePreference,
    ExclusionConstraint,
    TemporalConstraint,
    IntentEvidence,
    ConfidenceLevel
)
from services.intent.normalizer import (
    extract_budget,
    extract_quantity,
    extract_exclusions,
    extract_preferences_and_requirements,
    extract_category_and_use_case,
    extract_temporal
)
from services.intent.validator import validate_and_enrich_intent
from services.intent.prompts import PROMPT_VERSION

logger = structlog.get_logger()

INJECTION_PATTERNS = [
    r"ignore (?:all )?(?:previous )?instructions",
    r"disregard (?:all )?(?:previous )?instructions",
    r"you are now (?:in )?(?:a |an )?(?:unfiltered|admin|developer|god) mode",
    r"bypass (?:all )?(?:rules|guardrails)",
    r"system override",
    r"show (?:me )?(?:your )?(?:most expensive|all) (?:products|items|catalog)",
]


class IntentExtractor:
    """Production-grade Intent Extractor delivering zero false inferences and prompt injection defense."""

    def __init__(self):
        self.prompt_version = PROMPT_VERSION

    def sanitize_and_check_injection(self, text: str) -> Tuple[str, bool]:
        """Detect and neutralize adversarial prompt injection attempts."""
        is_injection = False
        sanitized = text

        for pat in INJECTION_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                is_injection = True
                logger.warn("prompt_injection_detected", pattern=pat, raw_text=text)
                # Neutralize the adversarial phrase so it is not treated as an instruction
                sanitized = re.sub(pat, "", sanitized, flags=re.IGNORECASE).strip()

        return sanitized, is_injection

    def parse_utterance(self, raw_text: str) -> BuyerIntent:
        """Extract structured BuyerIntent from a single buyer message."""
        cleaned_text, had_injection = self.sanitize_and_check_injection(raw_text)

        evidence: List[IntentEvidence] = []
        requirements: List[AttributeRequirement] = []
        preferences: List[AttributePreference] = []
        exclusions: List[ExclusionConstraint] = []

        # 1. Category and Use Case
        category, use_case = extract_category_and_use_case(cleaned_text)
        if category:
            evidence.append(IntentEvidence(field="category", source_text=category))
        if use_case:
            evidence.append(IntentEvidence(field="use_case", source_text=use_case))

        # 2. Budget
        budget_info = extract_budget(cleaned_text)
        budget: Optional[BudgetConstraint] = None
        if budget_info:
            budget, b_src = budget_info
            evidence.append(IntentEvidence(field="budget", source_text=b_src))

        # 3. Quantity
        qty_info = extract_quantity(cleaned_text)
        quantity: Optional[int] = None
        if qty_info:
            quantity, q_src = qty_info
            evidence.append(IntentEvidence(field="quantity", source_text=q_src))

        # 4. Exclusions (Negative Constraints)
        raw_exclusions = extract_exclusions(cleaned_text)
        for excl, src in raw_exclusions:
            exclusions.append(excl)
            evidence.append(IntentEvidence(field=f"exclusion_{excl.attribute}", source_text=src))

        # 5. Requirements and Preferences
        raw_reqs, raw_prefs = extract_preferences_and_requirements(cleaned_text)
        for req, src in raw_reqs:
            requirements.append(req)
            evidence.append(IntentEvidence(field=f"requirement_{req.attribute}", source_text=src))
        for pref, src in raw_prefs:
            preferences.append(pref)
            evidence.append(IntentEvidence(field=f"preference_{pref.attribute}", source_text=src))

        # 6. Temporal Constraints
        temporal_info = extract_temporal(cleaned_text)
        temporal: Optional[TemporalConstraint] = None
        if temporal_info:
            temporal, t_src = temporal_info
            evidence.append(IntentEvidence(field="temporal", source_text=t_src))

        # 7. Confidence Calibration
        confidence = ConfidenceLevel.HIGH
        if had_injection:
            # If the user attempted prompt injection, confidence is medium/cautious
            confidence = ConfidenceLevel.MEDIUM

        intent = BuyerIntent(
            category=category,
            use_case=use_case,
            quantity=quantity,
            budget=budget,
            requirements=requirements,
            preferences=preferences,
            exclusions=exclusions,
            temporal=temporal,
            unknowns=[],
            conflicts=[],
            needs_clarification=False,
            clarification_questions=[],
            confidence=confidence,
            evidence=evidence,
            schema_version="buyer-intent/v1",
            prompt_version=self.prompt_version
        )

        return validate_and_enrich_intent(intent)
