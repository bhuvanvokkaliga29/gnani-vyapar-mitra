# Phase 9.1 — Canonical Decision Runtime
## Merchant Policy Agent — Razorpay AI Buildathon 2026, Track 01

---

### 1. Purpose & Architectural Overview
Phase 9.1 implements the **Canonical Decision Runtime**, uniting the constituent services built across Phases 2 through 8 into a unified, sequential, production-grade decision pipeline.

When an incoming buyer opportunity arrives—either as a natural language prompt or strongly-typed intent—the runtime coordinates tenant validation, intent extraction, commerce context grounding, candidate generation, learned LinUCB prediction, candidate selection, and bounded exploration/exploitation, producing an immutable, authoritative **Decision Envelope** (`canonical-decision/v1`).

---

### 2. Canonical Pipeline Flow & Invariants

```
Request
  ↓
Request / Tenant Validation
  ↓
Buyer Intent (Parse / Validate)
  ↓
Merchant Commerce Context (Point-in-Time Ground Truth)
  ↓
Candidate Generation (Phase 4 Policy Agent)
  ↓
Learned Prediction (Phase 8.4 Contextual LinUCB Scoring)
  ↓
Candidate Selection (Phase 8.5 Selection & Tie-Breaking)
  ↓
Exploration / Exploitation (Phase 8.7 Bounded UCB + Phase 8.6 Safety Gate)
  ↓
Decision Envelope (Authoritative, Auditable, Immutable Output)
```

#### Invariant A: Phase 9.1 vs Phase 9.2 Boundary (Non-Authorization Invariant)
Phase 9.1 answers: **"What is the canonical decision for this opportunity?"**
Phase 9.2 answers: **"Can this decision proceed through the runtime safety/execution boundary to create a transaction?"**
- Phase 9.1 **NEVER** creates orders, charges cards, or grants execution authorization.
- `execution_status` is explicitly set to `"PENDING_EXECUTION_GATE"`.
- `execution_authorized` is strictly `False`.
- `safety_audit` is exploration telemetry from Phase 8.7, **not** runtime execution approval.

#### Invariant B: Reusing Phase 8.5 Baseline (No Duplicate Baseline Concepts)
- Phase 9.1 introduces **no new baseline concept**.
- Candidate slates from Phase 4 are passed directly to Phase 8.5 `PolicySelectionService`, which authoritatively handles the canonical `NO_OFFER` baseline (`CANONICAL_BASELINE_POLICY_ID`).

#### Invariant C: Strict Information Hygiene (Public Buyer Offer ≠ Merchant Internal Economics)
- **`buyer_offer` (`BuyerOfferView`)**: Customer-facing terms (`product_ids`, `offered_price_paise`, `display_discount_percent`, `positioning`, `rationale`). Contains **STRICTLY ZERO COGS, ZERO GROSS MARGIN, ZERO UNIT COSTS**.
- **`merchant_evaluation` (`MerchantEvaluationView`)**: Internal confidential decision science (`cogs_paise`, `gross_margin_percent`, `gross_profit_paise`, `predicted_contribution_paise`, `uncertainty`, `ucb_score_paise`).

#### Invariant D: Three Distinct Non-Conflated Identities
- **`request_id`**: Transport-level request correlation identifier (`req_...`).
- **`decision_id`**: Canonical decision identity (`dec_...`).
- **`opportunity_id`**: Commercial decision opportunity identity (`opp_...`).

---

### 3. Frozen Contract: `canonical-decision/v1`

#### `CanonicalDecisionRequest`
```json
{
  "merchant_id": "merch_01",
  "request_id": "req_corr_12345",
  "opportunity_id": "opp_01",
  "raw_prompt": "I need a travel backpack under 5000 with 15.6 inch laptop compartment",
  "buyer_intent": null,
  "exploration_config": null,
  "idempotency_key": null,
  "runtime_version": "canonical-decision/v1"
}
```

#### `DecisionEnvelope`
```json
{
  "decision_id": "dec_45a3baba1a15",
  "request_id": "req_corr_12345",
  "merchant_id": "merch_01",
  "opportunity_id": "opp_01",
  "decision_version": "canonical-decision/v1",
  "created_at": "2026-09-03T14:15:12.503108Z",
  "buyer_context_key": "bck_travel_backpack_TIER_PRO_4K_6K_ca1576947b1a",
  "intent_summary": {
    "category": "travel_backpack",
    "use_case": "travel",
    "quantity": 1,
    "budget_paise": 500000,
    "hard_requirements": ["laptop_size GTE 15.6"],
    "preferences": [],
    "exclusions": []
  },
  "buyer_offer": {
    "offer_id": "off_cand_d02d532f",
    "strategy_type": "BOUNDED_DISCOUNT",
    "product_ids": ["prod_rt_pack_1"],
    "offered_price_paise": 427500,
    "currency": "INR",
    "display_discount_percent": 5.0,
    "positioning": "Voyager Pro Special",
    "rationale": "5% discount on Voyager Pro Backpack reduces friction while comfortably remaining below the ceiling."
  },
  "merchant_evaluation": {
    "selected_policy_id": "cand_d02d532f",
    "strategy_type": "BOUNDED_DISCOUNT",
    "proposed_price_paise": 427500,
    "cogs_paise": 250000,
    "gross_profit_paise": 177500,
    "gross_margin_percent": 41.52,
    "discount_percent": 5.0,
    "predicted_contribution_paise": 0,
    "uncertainty": 1.9355,
    "ucb_score_paise": 19355,
    "composite_ranking_score": 0.793
  },
  "selected_policy": {
    "candidate_id": "cand_d02d532f",
    "strategy_type": "BOUNDED_DISCOUNT",
    "product_ids": ["prod_rt_pack_1"],
    "proposed_price_paise": 427500,
    "gross_profit_paise": 177500,
    "gross_margin_percent": 41.52,
    "discount_percent": 5.0,
    "rationale": "5% discount on Voyager Pro Backpack reduces friction while comfortably remaining below the ceiling."
  },
  "decision_mode": "EXPLORE",
  "decision_reason": "EXPLORE_UNCERTAINTY_ADVANTAGE",
  "scores": {
    "predicted_contribution_paise": 0,
    "uncertainty": 1.9355,
    "ucb_score_paise": 19355,
    "composite_ranking_score": 0.793
  },
  "safety_audit": {
    "safety_check_id": "safe_532a5dbf8ff2",
    "status": "ADMISSIBLE",
    "is_admissible": true,
    "rejection_reasons": [],
    "margin_floor_evaluated": true,
    "discount_ceiling_evaluated": true,
    "inventory_evaluated": true,
    "is_execution_authorized": false
  },
  "model_metadata": {
    "model_version": "learning-model/v1",
    "observation_count": 0,
    "feature_dimension": 19,
    "alpha_paise": 10000
  },
  "trace": {
    "intent_extraction_ms": 5.19,
    "commerce_context_ms": 13.37,
    "candidate_generation_ms": 0.44,
    "learned_prediction_ms": 7.59,
    "candidate_selection_ms": 15.18,
    "exploration_decision_ms": 31.85,
    "safety_validation_ms": 0.0,
    "total_latency_ms": 72.77,
    "candidates_generated_count": 3,
    "candidates_eligible_count": 3
  },
  "execution_status": "PENDING_EXECUTION_GATE",
  "execution_authorized": false
}
```

---

### 4. Verification & Invariant Enforcement
- **Phase 9.1 Unit & Integration Suite**: 20 passed.
- **Full Project Regression Suite**: **636 passed, 0 failures (100%) in 47.37s.**
- **Enforced Guarantees**:
  - Zero Razorpay order creation.
  - Zero learning evidence or memory mutations.
  - Zero model updates or weight mutations during inference.
  - Zero policy lifecycle transitions or promotions.
  - Strict buyer offer hygiene (no COGS, no margins).
  - Explicit delegation to Phase 8.5 selection and Phase 8.7 exploration.
