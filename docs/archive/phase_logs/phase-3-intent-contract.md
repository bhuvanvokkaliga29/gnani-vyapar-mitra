# Phase 3: BuyerIntent Contract Specification

**Schema Version**: `buyer-intent/v1`  
**Prompt Version**: `intent-extractor/v1`  
**Target Consumer**: Future Policy Agent (Phase 4)  

---

## 1. Architectural Role & Ground Truth Boundary

The `BuyerIntent` contract is the sole machine-readable interface between buyer communication and downstream commercial policy reasoning.

```text
Natural Language Buyer Message
              │
              ▼
   Phase 3 Intent Engine
(Semantic Extraction, Normalization, Conflict Detection)
              │
              ▼
         BuyerIntent (JSON/Pydantic)
              │
              ▼
   Future Policy Agent (Phase 4)
              │
              ▼
Evaluated against MerchantCommerceContext (Phase 2)
              │
              ▼
Candidate Commercial Strategies
```

---

## 2. Core Separation Invariants

1. **Requirements (HARD) vs. Preferences (SOFT)**:
   - A hard requirement must be satisfied by every candidate product proposal.
   - A soft preference is a nice-to-have used for ranking and utility scoring.
   - The engine must NEVER upgrade a soft preference (e.g. "I'd prefer black") to a hard requirement, or downgrade a hard requirement to a preference.
2. **Exclusions (Negative Constraints)**:
   - Things the buyer explicitly rejects (e.g. "No leather", "Anything except red") are preserved in `exclusions`.
3. **Budget Representation**:
   - Stored in integer paise (`BIGINT`, ₹1.00 = 100 paise).
   - Typed as `MAX` (ceiling), `RANGE` (min/max), `TARGET` (ideal point), or `APPROXIMATE` ("around 5k").
4. **Unknowns as First-Class Values**:
   - Missing fields must NOT be defaulted. If the buyer said "I need a backpack", the engine sets `category="backpack"` and explicitly lists missing fields in `unknowns: ["budget", "laptop_size"]`.
5. **No Commercial Decisions**:
   - Does NOT recommend products.
   - Does NOT check merchant inventory.
   - Does NOT apply merchant discounts.

---

## 3. Machine-Readable Schema Structure

```json
{
  "category": "travel_backpack",
  "use_case": "business_travel",
  "quantity": 1,
  "budget": {
    "amount_paise": 500000,
    "min_amount_paise": null,
    "max_amount_paise": 500000,
    "currency": "INR",
    "budget_type": "MAX",
    "constraint_type": "HARD"
  },
  "requirements": [
    {
      "attribute": "laptop_size",
      "operator": "GTE",
      "value": 15.0,
      "unit": "inch",
      "importance": "required"
    }
  ],
  "preferences": [
    {
      "attribute": "weight",
      "preference": "lightweight",
      "strength": "preferred"
    }
  ],
  "exclusions": [
    {
      "attribute": "material",
      "excluded_value": "leather",
      "importance": "required"
    }
  ],
  "temporal": {
    "delivery_deadline": "Friday",
    "usage_date": null
  },
  "unknowns": [],
  "conflicts": [],
  "needs_clarification": false,
  "clarification_questions": [],
  "confidence": "HIGH",
  "evidence": [
    {
      "field": "budget",
      "source_text": "under ₹5,000"
    },
    {
      "field": "laptop_size",
      "source_text": "fit my 15-inch laptop"
    }
  ],
  "schema_version": "buyer-intent/v1",
  "prompt_version": "intent-extractor/v1"
}
```
