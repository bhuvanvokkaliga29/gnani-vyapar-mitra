# Phase 6 Contract: AI Buyer Lab & Offer Selection Environment

**Specification Version**: `buyer-selection/v1`  
**Status**: ACTIVE & CONTRACT FROZEN  
**Scientific Distinction**: 
$$\text{Simulated Machine-Buyer Selection} \ne \text{Real Customer Conversion}$$
$$\text{Simulation Outcome} \ne \text{Observed Razorpay Transaction}$$

---

## 1. Architectural Role & Boundary

The AI Buyer Lab is a **controlled, offline simulation and evaluation environment** for observing machine-buyer decisions. It evaluates a set of candidate commercial offers against a structured `BuyerIntent v1` to determine:
1. Which offer a rational, constraint-respecting machine-buyer would select.
2. The observable, evidence-grounded attributes that drove the selection.

```text
BuyerIntent v1
       │
       ▼
AI Buyer Lab
       │
       ├── Hard Requirement Filter (GTE, LTE, EQ, CONTAINS)
       ├── Explicit Exclusion Filter (Zero Tolerance)
       ├── Budget Ceiling Filter (max_amount_paise)
       ├── Soft Preference Evaluator (Warranty, Delivery, Accessories)
       └── Deterministic Tie-Breaker (No Random Chance, No Merchant Favoritism)
       │
       ▼
BuyerSelectionResult v1
       ├── selected_offer_id
       ├── selection_reasons
       ├── rejected_offers
       ├── satisfied_preferences
       └── decision_trace
```

### Inviolable Boundaries
- **Zero Financial Execution**: Zero Razorpay credentials, zero API calls, zero payment transactions.
- **Zero Database Mutation**: Read-only, offline execution. No merchant database state is altered.
- **Zero Policy Training**: The Buyer Lab produces **evaluation evidence only**. It does not train policies, optimize parameters, or run multi-armed bandits (deferred to Phases 7 & 8).

---

## 2. Offer Visibility Boundary (`BuyerOffer`)

The machine buyer inspects **strictly buyer-visible data**. Internal merchant financial data is prohibited by schema (`extra="forbid"`):

| Buyer-Visible Attribute | Allowed? | Purpose |
|:---|:---:|:---|
| `offer_id` | ✅ | Identifier |
| `merchant_label` | ✅ | Public brand name |
| `product_name` | ✅ | Public product title |
| `category` | ✅ | Item classification |
| `price_paise` | ✅ | Buyer-visible total price in paise |
| `currency` | ✅ | Currency ISO code (INR) |
| `availability` | ✅ | Available-to-purchase status |
| `relevant_attributes` | ✅ | Physical specifications (laptop_size, weight, material) |
| `included_items` | ✅ | Included accessories or bundle components |
| `warranty_months` | ✅ | Public warranty length |
| `delivery_days` | ✅ | Estimated delivery timeframe |
| `incentives` | ✅ | Public perks (free shipping, pouches) |
| `is_synthetic` | ✅ | Distinguishes benchmark competitor fixtures |
| **`cogs_paise`** | ❌ **FORBIDDEN** | Internal merchant cost (Hidden) |
| **`margin_percent`** | ❌ **FORBIDDEN** | Internal profit margin (Hidden) |
| **`merchant_objective`** | ❌ **FORBIDDEN** | Internal strategy target (Hidden) |
| **`policy_score`** | ❌ **FORBIDDEN** | Internal policy ranking score (Hidden) |
| **`execution_approval`** | ❌ **FORBIDDEN** | Phase 5 execution token (Hidden) |

---

## 3. BuyerSelectionResult Schema (`buyer-selection/v1`)

```json
{
  "result_version": "buyer-selection/v1",
  "buyer_intent_version": "buyer-intent/v1",
  "simulation_version": "buyer-sim/v1",
  "scenario_id": "scen_A01_budget_filter",
  "selected_offer_id": "off_atlas_pass",
  "candidate_offer_ids": ["off_atlas_pass", "off_apex_fail"],
  "eligible_offer_ids": ["off_atlas_pass"],
  "rejected_offers": [
    {
      "offer_id": "off_apex_fail",
      "merchant_id": "merch_synth_apex",
      "rejection_reason": "BUDGET_EXCEEDED",
      "detail": "Offer price ₹4500.00 exceeds buyer budget ₹3500.00 by ₹1000.00.",
      "expected_value": "<= 350000 paise",
      "observed_value": "450000 paise"
    }
  ],
  "selection_reasons": ["HARD_REQUIREMENT_MATCH", "BUDGET_MATCH", "PREFERENCE_MATCH"],
  "selection_rationale": "Offer 'off_atlas_pass' from Atlas Travel Gear was the sole eligible offer satisfying all hard requirements and budget constraints at ₹2999.00.",
  "satisfied_preferences": ["warranty: 12 months"],
  "unmet_preferences": [],
  "hard_constraints_checked": ["AVAILABILITY", "BUDGET_CEILING_INR"],
  "decision_trace": [
    {
      "step": "AVAILABILITY_FILTER",
      "description": "Filtered out unavailable and out-of-stock items",
      "eligible_count_before": 2,
      "eligible_count_after": 2,
      "rejections_in_step": []
    },
    {
      "step": "BUDGET_FILTER",
      "description": "Filtered out offers exceeding stated budget ceiling",
      "eligible_count_before": 2,
      "eligible_count_after": 1,
      "rejections_in_step": ["off_apex_fail"]
    }
  ],
  "buyer_persona": "BALANCED",
  "generated_at": "2026-09-03T01:10:00Z"
}
```

---

## 4. Rejection and Selection Taxonomies

### Rejection Codes (`OfferRejectionCode`)
- `UNAVAILABLE`: Product is out of stock or marked unavailable.
- `CURRENCY_MISMATCH`: Offer currency does not match requested buyer currency.
- `BUDGET_EXCEEDED`: Price in paise strictly exceeds `max_amount_paise`.
- `HARD_REQUIREMENT_VIOLATED`: Fails explicit attribute requirement (e.g. laptop size, capacity).
- `EXCLUDED_BY_BUYER`: Contains an explicitly excluded material, color, brand, or feature.
- `MALFORMED_OFFER`: Offer metadata violates contract constraints.

### Selection Reasons (`SelectionTaxonomy`)
- `HARD_REQUIREMENT_MATCH`: Satisfies all mandatory specifications.
- `BUDGET_MATCH`: Complies with stated monetary ceiling.
- `PREFERENCE_MATCH`: Satisfies stated soft preferences.
- `TOTAL_VALUE_MATCH`: Highest composite utility among compliant offers.
- `BUNDLE_VALUE`: Included accessories provided superior utility.
- `WARRANTY_VALUE`: Extended warranty exceeded alternatives.
- `DELIVERY_VALUE`: Superior delivery speed turnaround.
- `LOWER_PRICE_AMONG_ELIGIBLE`: Lowest price among compliant offers.
- `DETERMINISTIC_TIE_BREAK`: Deterministic tie-breaker invoked between equivalent options.
- `NO_ELIGIBLE_OFFER`: All candidate offers failed hard criteria; zero offers selected.
