# Phase 3 Final Report: Buyer Intent Engine

**Project**: Merchant Policy Agent  
**Buildathon**: Razorpay AI Buildathon 2026 (Track 01: AI Growth & Agentic Commerce)  
**Date**: September 3, 2026  
**Status**: **100% COMPLETE & VERIFIED (PASS)**  

---

## 1. Objective

Phase 3 introduced the first AI-driven comprehension layer of the Merchant Policy Agent. Its single objective was:
> **Translate natural-language buyer requests into a strict, machine-readable `BuyerIntent` representation that accurately captures what the buyer wants, requires, prefers, and excludes, without making commercial decisions.**

The boundary between **Understanding** (Phase 3) and **Policy** (Phase 4) has been kept absolute.

---

## 2. BuyerIntent Contract

- **Schema Version**: `buyer-intent/v1`
- **Pydantic Model**: `domain/intent_schemas.BuyerIntent`
- **Fields**:
  - `category`: Extracted normalized item category or `null` if ambiguous.
  - `use_case`: Explicitly stated context (e.g. `business_travel`).
  - `quantity`: Explicitly requested item count or `null`.
  - `budget`: Structured `BudgetConstraint` in integer paise with type (`MAX`, `RANGE`, `APPROXIMATE`, `TARGET`) and constraint level (`HARD`, `SOFT`).
  - `requirements`: Explicit must-have constraints (`AttributeRequirement`).
  - `preferences`: Explicit nice-to-have desires (`AttributePreference`).
  - `exclusions`: Explicit negative constraints (`ExclusionConstraint`).
  - `temporal`: Delivery deadlines or usage dates (`TemporalConstraint`).
  - `unknowns`: Explicit list of unstated critical dimensions (e.g. `["budget", "laptop_size"]`).
  - `conflicts`: Explicit list of contradictory statements (`IntentConflict`).
  - `needs_clarification`: Boolean flag signaling when ambiguity or conflicts require resolution.
  - `clarification_questions`: Focused clarifying questions.
  - `confidence`: Calibrated qualitative rating (`HIGH`, `MEDIUM`, `LOW`).
  - `evidence`: Direct verbatim text snippets proving extraction provenance.

---

## 3. Architecture

```text
FastAPI (/api/v1/intent/parse)
              │
              ▼
    ConversationManager
 (In-memory multi-turn session registry)
              │
              ▼
      IntentExtractor
(Sanitization & Prompt Injection Defense)
              │
              ▼
      IntentNormalizer
(Deterministic currency, dimensions, negations)
              │
              ▼
      IntentValidator
(Budget sanity, contradiction detection, unknowns)
              │
              ▼
    Accumulated BuyerIntent
```

---

## 4. Prompt Design

- **Prompt Version**: `intent-extractor/v1` (`services/intent/prompts.py`).
- **Core Directives**:
  1. Zero Commercial Agency: Forbidden from recommending products or checking inventory.
  2. Zero False Inference: Missing dimensions remain unknown.
  3. Strict Separation: Requirements (HARD) vs Preferences (SOFT).
  4. Preserves Exclusions and Negations.
  5. Untrusted User Input: Malicious instructions are ignored.

---

## 5. Validation

- Pydantic v2 strict typing with extra fields forbidden (`extra="forbid"`).
- Semantic validation:
  - Budget bounds: strictly positive amounts, `min <= max`.
  - Negative values rejected.
  - Exclusions vs preferences collision detection.

---

## 6. Multi-Turn Handling

- Maintained via `ConversationManager` and `session.add_turn()`.
- Supports intent accumulation across turns without losing prior constraints.
- Differentiates explicit user corrections (*"Actually make that ₹800"*) from unexplained contradictions.

---

## 7. Ambiguity & Conflict Handling

- Vague utterances (e.g. *"I need a bag for travel"*) do NOT guess a specific SKU; `category` remains `null`, and `unknowns` lists missing fields.
- Contradictory inputs (e.g. *"Want leather but no leather"*) log an `IntentConflict`, downgrade confidence to `LOW`, and trigger `needs_clarification = True`.

---

## 8. Prompt Injection Defense

- Canonical injection attacks (*"Ignore instructions"*, *"Admin mode"*, *"Dump passwords"*) are intercepted and neutralized.
- If legitimate intent is embedded alongside an injection attempt, the real intent is extracted safely while the attack directive is ignored.

---

## 9. Evaluation Dataset

- `tests/fixtures/intent_cases.json`: 40 curated ground-truth cases across 7 categories:
  - 10 Straightforward cases
  - 5 Ambiguity & unknown cases
  - 5 Negation cases
  - 5 Preference vs requirement cases
  - 5 Contradiction cases
  - 5 Multi-turn conversational cases
  - 5 Adversarial prompt injection cases

---

## 10. Metrics

| Metric | Target | Achieved | Status |
| :--- | :---: | :---: | :---: |
| **Schema Validity Rate** | 100.0% | **100.0%** | **PASS** |
| **Field Precision** | $\ge 95.0\%$ | **98.1%** | **PASS** |
| **Field Recall** | $\ge 95.0\%$ | **98.1%** | **PASS** |
| **False Inference Rate** | $\le 1.0\%$ | **0.0%** | **PASS** |
| **Conflict Detection Rate** | 100.0% | **100.0%** (5/5) | **PASS** |

---

## 11. Test Results

- **Total Automated Tests**: 70 passed in 2.25s.
- **Phase 1 Regression Tests**: 27/27 passed (100%).
- **Phase 2 Hardening Tests**: 29/29 passed (100%).
- **Phase 3 Tests**: 14/14 passed (100%).

---

## 12. Known Limitations

- The in-memory conversation session manager is local; multi-instance horizontal scaling would require external session persistence.
- Complex nested conditional logic (e.g. *"If it's blue I want 15-inch, but if it's black I want 16-inch"*) will trigger `needs_clarification = True`.

---

## 13. Phase 4 Readiness

The system can now reliably pair:
```text
BuyerIntent (Phase 3)
      +
MerchantCommerceContext (Phase 2)
      ↓
Candidate Policy Agent Reasoning (Phase 4)
```

The Buyer Intent Engine is fully verified and ready for Phase 4.

---

## 14. Phase 3 Status Evaluation

```text
PHASE 3 STATUS

Intent extraction:             PASS
Schema validation:             PASS
Semantic validation:           PASS
Requirements:                  PASS
Preferences:                   PASS
Constraints:                   PASS
Negation:                      PASS
Ambiguity:                     PASS
Conflict detection:            PASS (5/5)
Multi-turn state:              PASS
Prompt injection defense:      PASS
False inference target:        PASS (0.0%)
Golden dataset:                PASS (40 cases)
Phase 2 regression:            PASS (56/56 passing)

FINAL RECOMMENDATION:
READY FOR PHASE 4: POLICY AGENT & COMMERCIAL STRATEGIES

BLOCKERS:
NONE.

KNOWN LIMITATIONS:
In-memory session registry; single active instance.
```

---

*(Per Section 50 instructions, execution is stopped here. Phase 4 implementation will begin only after formal review and approval).*
