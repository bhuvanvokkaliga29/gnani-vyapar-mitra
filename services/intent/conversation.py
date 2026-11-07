"""Multi-Turn Conversational Memory, Intent Merging, and Conflict Resolution."""

import uuid
from typing import Dict, Optional, List, Tuple
from domain.intent_schemas import (
    BuyerIntent,
    IntentConflict,
    BudgetConstraint,
    AttributeRequirement,
    AttributePreference,
    ExclusionConstraint,
    ConfidenceLevel
)
from services.intent.validator import validate_and_enrich_intent


class ConversationSession:
    """Tracks accumulated buyer intent across a multi-turn dialogue."""

    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.turns: List[str] = []
        self.accumulated_intent: Optional[BuyerIntent] = None

    def add_turn(self, utterance: str, new_intent: BuyerIntent) -> BuyerIntent:
        self.turns.append(utterance)
        if self.accumulated_intent is None:
            self.accumulated_intent = new_intent
        else:
            self.accumulated_intent = merge_intents(
                base=self.accumulated_intent,
                incoming=new_intent,
                utterance=utterance
            )
        return self.accumulated_intent


class ConversationManager:
    """In-memory session registry for multi-turn intent tracking."""

    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}

    def get_or_create_session(self, conversation_id: Optional[str] = None) -> ConversationSession:
        if not conversation_id:
            conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        if conversation_id not in self._sessions:
            self._sessions[conversation_id] = ConversationSession(conversation_id)
        return self._sessions[conversation_id]

    def reset(self):
        self._sessions.clear()


def merge_intents(base: BuyerIntent, incoming: BuyerIntent, utterance: str) -> BuyerIntent:
    """Merge an incoming turn's intent into the accumulated baseline intent.

    Applies conflict detection, explicit update semantics, and unknown resolution.
    """
    t_lower = utterance.lower()
    is_explicit_correction = any(w in t_lower for w in ["actually", "make that", "change", "rather", "instead", "okay"])

    # 1. Merge Category
    category = incoming.category or base.category

    # 2. Merge Use Case
    use_case = incoming.use_case or base.use_case

    # 3. Merge Quantity
    quantity = incoming.quantity or base.quantity

    # 4. Merge Budget & Detect Contradictions
    budget = base.budget
    conflicts: List[IntentConflict] = list(base.conflicts)

    if incoming.budget:
        if base.budget and base.budget.max_amount_paise != incoming.budget.max_amount_paise:
            if is_explicit_correction:
                # User intentionally updated their budget: "Actually make that 4000"
                budget = incoming.budget
            else:
                # Unexplained discrepancy -> record conflict
                conflicts.append(
                    IntentConflict(
                        field="budget",
                        previous_value=base.budget.max_amount_paise,
                        new_value=incoming.budget.max_amount_paise,
                        reason="New budget contradicts previously stated budget without explicit correction marker"
                    )
                )
                budget = incoming.budget
        else:
            budget = incoming.budget

    # 5. Merge Requirements (Avoid duplicates)
    req_map = {r.attribute: r for r in base.requirements}
    for r in incoming.requirements:
        req_map[r.attribute] = r
    merged_requirements = list(req_map.values())

    # 6. Merge Preferences
    pref_map = {p.attribute: p for p in base.preferences}
    for p in incoming.preferences:
        pref_map[p.attribute] = p
    merged_preferences = list(pref_map.values())

    # 7. Merge Exclusions
    excl_map = {(e.attribute, e.excluded_value): e for e in base.exclusions}
    for e in incoming.exclusions:
        excl_map[(e.attribute, e.excluded_value)] = e
    merged_exclusions = list(excl_map.values())

    # 8. Merge Temporal
    temporal = incoming.temporal or base.temporal

    # 9. Merge Evidence
    evidence = base.evidence + incoming.evidence

    merged_intent = BuyerIntent(
        category=category,
        use_case=use_case,
        quantity=quantity,
        budget=budget,
        requirements=merged_requirements,
        preferences=merged_preferences,
        exclusions=merged_exclusions,
        temporal=temporal,
        unknowns=[],
        conflicts=conflicts,
        needs_clarification=len(conflicts) > 0,
        clarification_questions=[],
        confidence=ConfidenceLevel.HIGH,
        evidence=evidence
    )

    return validate_and_enrich_intent(merged_intent)
