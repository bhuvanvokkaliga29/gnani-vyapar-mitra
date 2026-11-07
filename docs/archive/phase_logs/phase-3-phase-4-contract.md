# Phase 3 → Phase 4 Contract Specification

**Date**: September 3, 2026  
**Status**: FROZEN  
**Contract Version**: `buyer-intent/v1`

---

## Purpose

This document defines the **exact interface** that Phase 4 (Policy Agent) will consume from Phase 3 (Buyer Intent Engine). Phase 4 MUST NOT reinterpret raw buyer messages. Phase 4 receives only the structured `BuyerIntent` object.

## Contract: Phase 3 Output → Phase 4 Input

### Data Flow

```
Buyer → [Raw Text] → Phase 3 Intent Engine → [BuyerIntent v1] → Phase 4 Policy Agent
                                                                          ↓
                                                              [MerchantCommerceContext]
                                                                          ↓
                                                              Policy Decision (Phase 4)
```

### Interface Object: `BuyerIntent`

Phase 4 receives a `BuyerIntent` Pydantic model with the following frozen fields:

```python
class BuyerIntent(BaseModel):
    category: Optional[str]                    # Normalized product category
    use_case: Optional[str]                    # Explicitly stated use-case
    quantity: Optional[int]                    # Explicit quantity (None if unstated)
    budget: Optional[BudgetConstraint]         # Budget constraint in paise
    requirements: List[AttributeRequirement]   # HARD constraints
    preferences: List[AttributePreference]     # SOFT preferences
    exclusions: List[ExclusionConstraint]      # Negative constraints
    temporal: Optional[TemporalConstraint]     # Delivery deadline
    unknowns: List[str]                        # Unspecified critical dimensions
    conflicts: List[IntentConflict]            # Detected contradictions
    needs_clarification: bool                  # True if ambiguity requires resolution
    clarification_questions: List[str]         # Suggested clarification questions
    confidence: ConfidenceLevel                # HIGH / MEDIUM / LOW
    evidence: List[IntentEvidence]             # Audit trail back to source text
    schema_version: str                        # "buyer-intent/v1"
    prompt_version: str                        # "intent-extractor/v1"
```

### Phase 4 Obligations

1. **No raw text reinterpretation**: Phase 4 MUST NOT parse the buyer's original message. All buyer intent comes through `BuyerIntent`.
2. **Respect constraint types**: `requirements` are HARD (must-satisfy). `preferences` are SOFT (nice-to-have). Phase 4 MUST NOT upgrade preferences to requirements.
3. **Respect unknowns**: If `unknowns` contains `"budget"`, Phase 4 MUST NOT assume a default budget.
4. **Respect conflicts**: If `needs_clarification` is True, Phase 4 SHOULD request clarification before making irreversible decisions.
5. **Schema version check**: Phase 4 SHOULD assert `schema_version == "buyer-intent/v1"` and reject incompatible versions.
6. **Currency awareness**: Budget amounts are in **paise** (integer). `currency` field indicates the denomination. Phase 4 MUST use the currency field for cross-currency scenarios.

### Phase 3 Guarantees to Phase 4

1. **Zero false inference**: If the buyer did not state an attribute, it will be `None` or absent. Never fabricated.
2. **Deterministic output**: Same input text always produces the same `BuyerIntent`.
3. **Evidence trace**: Every extracted field has a corresponding `IntentEvidence` entry linking back to the verbatim source text.
4. **Prompt injection defense**: Adversarial content is neutralized before extraction. Phase 4 does not need to re-sanitize.
5. **Contradiction detection**: Budget conflicts and preference↔exclusion collisions are flagged in `conflicts`.

### API Endpoint

```
POST /api/v1/intent/parse
Content-Type: application/json

Request:  { "message": "...", "conversation_id": "..." }
Response: { "intent": BuyerIntent, "conversation_id": "...", "turn_index": N, "processing_time_ms": F }
```

### Integration Pattern for Phase 4

```python
# Phase 4 Policy Agent consumes BuyerIntent without database access to Phase 3
def make_policy_decision(
    buyer_intent: BuyerIntent,
    commerce_context: MerchantCommerceContext
) -> PolicyDecision:
    # Phase 4 logic here — operates ONLY on these two inputs
    assert buyer_intent.schema_version == "buyer-intent/v1"
    ...
```

## Breaking Change Policy

Any change to `BuyerIntent` that would alter Phase 4's expected input MUST:

1. Bump `schema_version` to `v2`
2. Provide a migration guide
3. Maintain backward compatibility for at least one release cycle
