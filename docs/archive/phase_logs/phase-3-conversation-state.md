# Phase 3: Conversational State & Multi-Turn Intent Merging

This document defines how conversational dialogue is accumulated, how user corrections are handled, and how contradictions are identified in the Buyer Intent Engine.

---

## 1. Multi-Turn Accumulation Flow

A buyer rarely provides all requirements in a single utterance. The Intent Engine maintains state across conversation turns:

```text
Turn 1: "I need a travel backpack."
      ↓
Intent: category = "travel_backpack", unknowns = ["budget", "laptop_size"]

Turn 2: "It needs to fit my 15-inch laptop."
      ↓
Intent: category = "travel_backpack", requirements = [laptop_size >= 15.0], unknowns = ["budget"]

Turn 3: "And I want to keep it under ₹5,000."
      ↓
Intent: category = "travel_backpack", requirements = [laptop_size >= 15.0], budget_max = 500000 paise, unknowns = []
```

---

## 2. Intent Merge Rules

When a new utterance arrives within an existing `conversation_id`:
1. **Preservation of Existing Attributes**: Attributes extracted in prior turns are retained unless explicitly modified.
2. **Requirement Non-Duplication**: If the user repeats or refines a requirement (e.g. laptop size), the latest explicit value updates the requirement rather than appending duplicate constraints.
3. **Additive Preferences**: Multiple preferences across turns (e.g. Turn 1: "lightweight", Turn 2: "black") are unioned into `preferences`.

---

## 3. Conflict Detection vs. User Correction

The engine distinguishes between an **unexplained contradiction** and an **explicit user correction**:

### A. Explicit Correction
- Phrasing with correction markers: *"Actually"*, *"Make that"*, *"Change that to"*, *"Rather"*, *"Instead"*.
- **Behavior**: The new value supersedes the prior value.
- **Example**:
  - Turn 1: *"Under ₹5,000."*
  - Turn 2: *"Actually, make that ₹4,000."*
  - Result: `budget.max_amount_paise = 400000`. No conflict flagged.

### B. Unexplained Contradiction
- The user provides mutually incompatible constraints without a correction marker.
- **Behavior**: An `IntentConflict` record is created, `needs_clarification` is set to `True`, and a targeted question is generated.
- **Example**:
  - Turn 1: *"Under ₹5,000."*
  - Turn 2: *"I want the ₹7,000 model."*
  - Result:
    ```json
    {
      "conflicts": [
        {
          "field": "budget",
          "previous_value": 500000,
          "new_value": 700000,
          "reason": "New budget contradicts previously stated budget without explicit correction marker"
        }
      ],
      "needs_clarification": true,
      "confidence": "LOW"
    }
    ```
