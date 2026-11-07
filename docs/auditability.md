# Auditability Model & Decision Lineage

This document specifies the immutable audit trail and decision lineage architecture, ensuring that every autonomous decision and financial transaction can be fully explained, inspected, and verified.

---

## 1. The Four Core Auditing Questions

Any auditor, merchant, or hackathon judge must be able to inspect the system and answer four fundamental questions for any event:

1. **Why did the agent make this commercial decision?**
   - *Audit Lineage*: The exact buyer intent string, extracted constraints, historical variant performance, and the LLM's structured reasoning prompt and qualitative justification.
2. **Which deterministic rules allowed it?**
   - *Audit Lineage*: The exact validation record proving the proposed basket satisfied the merchant's margin floor, discount ceiling, buyer budget, and real-time inventory count.
3. **Which Razorpay transaction resulted?**
   - *Audit Lineage*: The Razorpay `order_id`, `payment_id`, captured currency amount in paise, and matching HMAC-verified webhook event.
4. **What evidence caused the policy to change?**
   - *Audit Lineage*: The statistical update record showing the change in sample size, conversion rate, and empirical contribution per shopper that shifted the multi-armed bandit weights.

---

## 2. Comprehensive Audit Event Schema

Every agent execution produces an end-to-end `AgentExecutionTrace` persisted in PostgreSQL:

```json
{
  "run_id": "run_9a8b7c6d5e",
  "timestamp": "2026-09-03T12:00:00.123Z",
  "merchant_id": "merch_artisanal_brew_99",
  "buyer_id": "buyer_agent_ai_88",
  "intent_id": "int_7f8a9b1c2d",
  "policy_id": "pol_config_default_v2",
  "experiment_id": "exp_espresso_bundling_v1",
  "experiment_variant": "VARIANT_B",
  "buyer_raw_query": "Need a high pressure espresso setup with grinder under ₹18,000 with quick delivery",
  "extracted_constraints": {
    "max_budget_paise": 1800000,
    "required_categories": ["kitchen_appliances"],
    "required_attributes": { "pressure_bar_min": 15 }
  },
  "candidate_strategy": {
    "proposed_items": [
      { "sku": "CF-MKR-PRO", "qty": 1, "unit_price_paise": 1400000 },
      { "sku": "CF-GRN-BURR", "qty": 1, "unit_price_paise": 300000 }
    ],
    "bundle_discount_paise": 100000,
    "total_proposed_price_paise": 1600000,
    "value_proposition": "Complete 15-bar home barista kit with burr grinder + 2-yr warranty"
  },
  "qualitative_reasoning": "AI buyer asked for setup under 18k with grinder. Bundling grinder at 3k with 1k discount hits 16k, leaving 2k budget headroom and moving accessory stock.",
  "validation_result": {
    "is_approved": true,
    "computed_margin_pct": 31.25,
    "margin_floor_pct": 25.0,
    "effective_discount_pct": 5.88,
    "discount_ceiling_pct": 20.0,
    "buyer_budget_paise": 1800000,
    "inventory_verified": true,
    "rejection_reasons": []
  },
  "approved_action": "CREATE_RAZORPAY_ORDER",
  "razorpay_order_id": "order_NXK1829abcD",
  "razorpay_receipt": "dec_9e8d7c6b5a",
  "razorpay_payment_id": "pay_PLM992817x",
  "webhook_event_id": "evt_rzp_99182377",
  "outcome": {
    "status": "CAPTURED",
    "captured_amount_paise": 1600000,
    "total_cogs_paise": 1100000,
    "modeled_fees_paise": 32000,
    "observed_contribution_paise": 468000
  },
  "policy_update": {
    "previous_variant_cps_paise": 442000,
    "new_variant_cps_paise": 448500,
    "sample_count": 42
  }
}
```

---

## 3. Storage & Immutability Rules

- **Append-Only Table**: Audit records are inserted into `audit_events` and `agent_decisions`. Direct `UPDATE` and `DELETE` operations are disabled on audit tables via database triggers.
- **Relational Integrity**: Foreign keys ensure every transaction outcome points directly to an `agent_decisions` entry, which points to an `intents` entry.
- **Structured Logging**: Every step logs a structured JSON event via `structlog` containing `run_id`, allowing correlation across application logs, database tables, and Razorpay dashboard webhooks.
