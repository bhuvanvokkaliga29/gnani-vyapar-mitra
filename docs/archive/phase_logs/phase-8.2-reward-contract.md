# Phase 8.2 Contract: Learning Objective & Reward Layer

**Contract Version**: `merchant-reward/v1`  
**Formula Version**: `contribution-formula/v1`  
**Status**: ACTIVE & CONTRACT FROZEN  
**Role**: Authoritative mathematical and contractual definition of the commercial learning objective.

---

## 1. Architectural Boundary

Phase 8.2 defines the **exact mathematical learning objective** that later learning components (Phases 8.3 and 8.4) will consume. It evaluates authoritative evidence from Phase 8.1 and computes the merchant's realized economic value per opportunity.

```text
Phase 7 Controlled Policy Experiment
                 │
       ExperimentObservation
                 │
         ExperimentResult
                 │
                 ▼
Phase 8.1 PolicyLearningEvidence (merchant-learning/v1)
                 │
                 ▼
Phase 8.2 PolicyOpportunityReward (merchant-reward/v1)
                 │
                 ▼
Phase 8.2 AggregatedRewardObjective (merchant-reward/v1)
                 │
════════════════════════════════════════════════════════════════════════════
                     FIREWALL / HARD STOP BOUNDARY
   (Zero bandits, zero RL, zero policy updates, zero exploration/exploitation)
════════════════════════════════════════════════════════════════════════════
                 │
     [Deferred to Phase 8.3]: Policy Memory & Historical Retrieval
     [Deferred to Phase 8.4]: Autonomous Policy Learning Algorithm
```

---

## 2. PolicyOpportunityReward Contract (`merchant-reward/v1`)

```json
{
  "reward_id": "rwd_7a1b3c5e8f9d",
  "reward_version": "merchant-reward/v1",
  "formula_version": "contribution-formula/v1",
  "merchant_id": "merch_atlas_travel",
  "opportunity_id": "exp_4b2c7e189a01:scen_01:TREATMENT",
  "buyer_context_key": "bck_travel_backpack_TIER_MID_2K_4K_7e3a9c4f12d0",
  "policy_id": "prop_treat_atlas_bundle",
  "policy_version": "merchant-policy/v1",
  "experiment_id": "exp_4b2c7e189a01",
  "experiment_version": "policy-experiment/v1",
  "variant": "TREATMENT",
  "evidence_id": "evi_8f7b2c9a1d3e",
  "evidence_source": "TEST_MODE_OBSERVED",
  "outcome_type": "PAYMENT_SUCCESS",
  "reward_state": "REWARD_ELIGIBLE",
  "is_admissible": true,
  "inadmissibility_reasons": [],
  "realized_revenue_paise": 349900,
  "realized_cogs_paise": 170000,
  "realized_discount_paise": 0,
  "reward_contribution_paise": 179900,
  "margin_percent": 51.41,
  "idempotency_key": "rwd_evi_obs_exp_4b2c7e189a01_scen_01_TREATMENT",
  "evaluated_at": "2026-09-03T13:00:00Z"
}
```

---

## 3. AggregatedRewardObjective Contract (`merchant-reward/v1`)

```json
{
  "objective_id": "obj_9f8e7d6c5b4a",
  "objective_version": "merchant-reward/v1",
  "formula_version": "contribution-formula/v1",
  "merchant_id": "merch_atlas_travel",
  "policy_id": "prop_treat_atlas_bundle",
  "policy_version": "merchant-policy/v1",
  "buyer_context_key": "bck_travel_backpack_TIER_MID_2K_4K_7e3a9c4f12d0",
  "experiment_id": "exp_4b2c7e189a01",
  "variant": "TREATMENT",
  "metric_type": "OBSERVED_CONTRIBUTION_PER_SHOPPER",
  "total_opportunities_evaluated": 50,
  "eligible_opportunity_count": 48,
  "ineligible_opportunity_count": 2,
  "order_created_count": 25,
  "successful_payment_count": 24,
  "successful_payment_rate": 0.5000,
  "total_realized_revenue_paise": 8397600,
  "total_realized_cogs_paise": 4080000,
  "total_realized_discount_paise": 0,
  "total_contribution_paise": 4317600,
  "contribution_per_shopper_paise": 89950,
  "contribution_per_shopper_decimal": 89950.0,
  "average_margin_percent": 51.41,
  "aggregation_key": "merch_atlas_travel:bck_travel_backpack_TIER_MID_2K_4K_7e3a9c4f12d0:prop_treat_atlas_bundle:merchant-policy/v1",
  "calculated_at": "2026-09-03T13:05:00Z"
}
```

---

## 4. Reward State Taxonomy

| State | Meaning | Admissible in Denominator? | Contribution |
|:---|:---|:---:|:---:|
| **`REWARD_ELIGIBLE`** | Converted transaction satisfying all guardrails. | Yes | Positive or negative integer paise |
| **`REWARD_ZERO`** | Eligible non-purchase (e.g. `NO_SELECTION`, unpaid order). | Yes | Exactly 0 paise |
| **`REWARD_GUARDRAIL_VIOLATION`** | Commercial guardrail failure (margin floor, discount ceiling). Retained in denominator to prevent selection bias. | **Yes** (Included in Denominator) | Exactly 0 paise (`is_safety_violation=True`) |
| **`REWARD_INELIGIBLE`** | Inadmissible due to corrupt pipeline criteria (e.g. insufficient sample). | **No** (Excluded) | Excluded |
| **`REWARD_DATA_UNAVAILABLE`**| Missing mandatory cost/revenue inputs. | **No** (Excluded) | Excluded |
| **`REWARD_INVALID`** | Corrupt or contradictory evidence. | **No** (Excluded) | Excluded |
