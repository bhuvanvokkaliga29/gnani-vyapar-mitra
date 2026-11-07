# Product Contract & Interface Specifications

This document defines the strict typed contracts governing the boundaries between the Merchant, the Merchant Policy Agent, the Deterministic Policy Engine, and the Transaction Feedback Layer.

---

## 1. Merchant-Provided Inputs

> [!IMPORTANT]
> **Data Origin Boundary**:
> Razorpay does **not** maintain internal merchant accounting records such as unit COGS, supplier costs, or multi-echelon inventory limits. All product cost structures, margin thresholds, and catalog metadata are provided directly by the merchant.

### 1.1 Product Catalog & Unit Economics (`MerchantProduct`)
```json
{
  "product_id": "prod_coffee_maker_01",
  "sku": "CF-MKR-PRO",
  "name": "Barista Pro Espresso Machine",
  "category": "kitchen_appliances",
  "attributes": {
    "wattage": 1500,
    "color": "stainless_steel",
    "pressure_bar": 15,
    "warranty_months": 24
  },
  "base_price_paise": 1500000,
  "cogs_paise": 800000,
  "inventory_count": 45,
  "is_active": true,
  "created_at": "2026-09-01T10:00:00Z"
}
```

### 1.2 Product Relationships & Compatibility (`ProductRelationship`)
```json
{
  "primary_product_id": "prod_coffee_maker_01",
  "related_product_id": "prod_coffee_grinder_02",
  "relationship_type": "compatible_accessory",
  "recommended_bundle_affinity": 0.85
}
```

### 1.3 Merchant Guardrails & Business Objectives (`MerchantPolicyConfig`)
```json
{
  "merchant_id": "merch_artisanal_brew_99",
  "currency": "INR",
  "global_margin_floor_pct": 25.0,
  "max_discount_ceiling_pct": 20.0,
  "allow_cross_sku_bundling": true,
  "max_items_per_bundle": 4,
  "priority_categories": ["kitchen_appliances", "beans"],
  "business_objective": "maximize_contribution_margin"
}
```

---

## 2. Agent Runtime Inputs

### 2.1 AI Buyer Intent (`BuyerIntent`)
Received from an AI buyer agent (e.g., via Agentic Commerce Protocol query or API endpoint):
```json
{
  "intent_id": "int_7f8a9b1c2d",
  "buyer_persona": "budget_sensitive",
  "natural_language_query": "Need a high pressure espresso setup with grinder under ₹18,000 with quick delivery",
  "extracted_constraints": {
    "max_budget_paise": 1800000,
    "required_categories": ["kitchen_appliances"],
    "required_attributes": {
      "pressure_bar_min": 15
    },
    "delivery_speed_priority": "high",
    "gift_wrapping_requested": false
  },
  "timestamp": "2026-09-03T12:00:00Z"
}
```

### 2.2 Historical Policy Performance & Experiment Context (`AgentContext`)
```json
{
  "experiment_id": "exp_espresso_bundling_v1",
  "assigned_variant": "VARIANT_B",
  "historical_baseline": {
    "control_ecps_paise": 120000,
    "historical_sample_size": 150
  },
  "available_inventory_snapshot": {
    "prod_coffee_maker_01": 45,
    "prod_coffee_grinder_02": 18
  }
}
```

---

## 3. Agent Runtime Outputs (Proposals)

> [!WARNING]
> The Agent output is a **Candidate Commercial Proposal**. It is NOT executable until validated and verified by the Deterministic Policy Engine.

### 3.1 Candidate Policy Output (`CandidateCommercialStrategy`)
```json
{
  "candidate_id": "cand_9e8d7c6b5a",
  "intent_id": "int_7f8a9b1c2d",
  "experiment_variant": "VARIANT_B",
  "proposed_items": [
    {
      "product_id": "prod_coffee_maker_01",
      "quantity": 1,
      "proposed_unit_price_paise": 1400000
    },
    {
      "product_id": "prod_coffee_grinder_02",
      "quantity": 1,
      "proposed_unit_price_paise": 300000
    }
  ],
  "bundle_discount_paise": 100000,
  "total_proposed_price_paise": 1600000,
  "value_proposition": "Complete 15-bar home barista kit with companion burr grinder + complimentary 2-year extended warranty",
  "qualitative_reasoning": "AI buyer requested espresso setup under ₹18,000. Standalone machine is ₹15,000. Bundling compatible grinder at ₹3,000 with a ₹1,000 bundle discount lands at ₹16,000, remaining well under the ₹18,000 budget while securing grinder inventory movement.",
  "predicted_selection_probability": 0.42,
  "predicted_contribution_paise": 450000
}
```

---

## 4. Deterministic Engine Validation Output

### 4.1 Verification Contract (`ValidationResult`)
Produced by the deterministic engine without LLM involvement:
```json
{
  "validation_id": "val_1a2b3c4d",
  "candidate_id": "cand_9e8d7c6b5a",
  "is_approved": true,
  "rejection_reasons": [],
  "computed_financials": {
    "total_revenue_paise": 1600000,
    "total_cogs_paise": 1100000,
    "effective_discount_pct": 5.88,
    "gross_margin_pct": 31.25,
    "modeled_payment_fee_paise": 32000,
    "deterministic_contribution_paise": 468000
  },
  "guardrail_checks": {
    "margin_floor_passed": true,
    "discount_ceiling_passed": true,
    "buyer_budget_passed": true,
    "inventory_available_passed": true
  },
  "approved_at": "2026-09-03T12:00:01Z"
}
```

---

## 5. Execution & Transaction Feedback Contract

### 5.1 Razorpay Order Request Contract (`RazorpayOrderPayload`)
Constructed deterministically upon validation approval:
```json
{
  "amount": 1600000,
  "currency": "INR",
  "receipt": "dec_9e8d7c6b5a",
  "payment_capture": 1,
  "notes": {
    "candidate_id": "cand_9e8d7c6b5a",
    "intent_id": "int_7f8a9b1c2d",
    "merchant_id": "merch_artisanal_brew_99",
    "experiment_variant": "VARIANT_B"
  }
}
```

### 5.2 Transaction Outcome & Verification (`TransactionOutcome`)
Recorded when the primary webhook signal is received or API reconciliation occurs:
```json
{
  "outcome_id": "out_33445566",
  "candidate_id": "cand_9e8d7c6b5a",
  "razorpay_order_id": "order_NXK1829abcD",
  "razorpay_payment_id": "pay_PLM992817x",
  "transaction_status": "captured",
  "captured_amount_paise": 1600000,
  "observed_cogs_paise": 1100000,
  "modeled_costs_paise": 32000,
  "observed_contribution_paise": 468000,
  "event_id": "evt_rzp_99182377",
  "verification_method": "webhook_hmac_sha256",
  "reconciled_via_api": false,
  "created_at": "2026-09-03T12:00:15Z"
}
```

### 5.3 Policy Update Feedback (`PolicyLearningUpdate`)
Feedforward to the Merchant Policy Store:
```json
{
  "policy_update_id": "pol_upd_7788",
  "experiment_id": "exp_espresso_bundling_v1",
  "variant": "VARIANT_B",
  "sample_count_increment": 1,
  "observed_conversion": 1,
  "observed_contribution_paise": 468000,
  "updated_expected_contribution_paise": 448500,
  "updated_selection_probability": 0.435
}
```
