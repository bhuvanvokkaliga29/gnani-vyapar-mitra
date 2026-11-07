# Phase 8.1 Contract: Merchant Policy Learning Evidence

**Contract Version**: `merchant-learning/v1`  
**Status**: ACTIVE & CONTRACT FROZEN  
**Role**: Authoritative firewall between experimentation/simulation and future policy learning.

---

## 1. Architectural Firewall

The future commercial policy learner (deferred to later Phase 8 sub-phases) must consume **strictly validated `PolicyLearningEvidence`**. It is forbidden from consuming raw LLM outputs, raw `BuyerIntent` strings, raw webhook payloads, or unvalidated experiment inputs.

```text
Phase 7 Experiment
       │
ExperimentObservation
       │
ExperimentResult
       │
       ▼
Phase 8.1 PolicyLearningEvidence (merchant-learning/v1)
       │
══════════════════════════════════════════════════════════════════
               FIREWALL / HARD STOP BOUNDARY
  (No bandits, no RL, no rewards, no policy updates, no n8n)
══════════════════════════════════════════════════════════════════
       │
[Deferred to Phase 8.2]: Reward Definition
[Deferred to Phase 8.3]: Policy Memory & Retrieval
[Deferred to Phase 8.4]: Autonomous Policy Learning Algorithm
```

---

## 2. PolicyLearningEvidence Contract (`merchant-learning/v1`)

```json
{
  "evidence_id": "evi_8f7b2c9a1d3e",
  "evidence_version": "merchant-learning/v1",
  "merchant_id": "merch_atlas_travel",
  "experiment_id": "exp_4b2c7e189a01",
  "experiment_version": "policy-experiment/v1",
  "experiment_observation_id": "obs_9f8e7d6c5b4a",
  "scenario_id": "scen_01",
  "policy_id": "prop_treat_atlas_bundle",
  "policy_version": "merchant-policy/v1",
  "variant": "TREATMENT",
  "buyer_context_key": "bck_travel_backpack_TIER_MID_2K_4K_7e3a9c4f12d0",
  "buyer_intent_version": "buyer-intent/v1",
  "buyer_selection_result_id": "scen_01",
  "simulation_version": "buyer-selection/v1",
  "execution_id": null,
  "provider_order_id": null,
  "verified_payment_id": null,
  "source": "SIMULATED",
  "outcome_type": "SIMULATED_SELECTION",
  "sample_size": 1,
  "is_selected": true,
  "expected_revenue_paise": 349900,
  "expected_contribution_paise": 179900,
  "observed_revenue_paise": null,
  "observed_contribution_paise": null,
  "margin_percent": 51.41,
  "guardrail_results": [
    {
      "guardrail_type": "MIN_MARGIN_PERCENT",
      "threshold_value": 40.0,
      "observed_value": 51.41,
      "passed": true,
      "detail": "Observed margin 51.4% meets floor 40.0%"
    }
  ],
  "evidence_status": "VALID",
  "lifecycle_state": "LEARNING_ELIGIBLE",
  "learning_eligible": true,
  "eligibility_reasons": [
    "Evidence verified: valid quality, complete provenance, satisfied guardrails."
  ],
  "aggregation_key": "merch_atlas_travel:bck_travel_backpack_TIER_MID_2K_4K_7e3a9c4f12d0:prop_treat_atlas_bundle:merchant-policy/v1",
  "idempotency_key": "evi_obs_exp_4b2c7e189a01_scen_01_TREATMENT",
  "observed_at": "2026-09-03T12:05:00Z",
  "created_at": "2026-09-03T12:55:00Z"
}
```

---

## 3. Source Taxonomy

| Source | Description | Availability in Current Track |
|:---|:---|:---:|
| **`SIMULATED`** | Generated from offline AI Buyer Lab (Phase 6) multi-alternative simulations. | Available & Active |
| **`TEST_MODE_OBSERVED`** | Generated from Phase 5 Execution Gate traversal into Razorpay Test Mode. | Available & Active |
| **`PRODUCTION_OBSERVED`** | Real-world customer transactions and live payments. | **Unsupported & Forbidden** |

---

## 4. Outcome Taxonomy & Core Invariants

| Outcome Type | Description | Required Verification |
|:---|:---|:---|
| **`SIMULATED_SELECTION`** | Merchant offer chosen by AI Buyer Lab in simulated evaluation. | `is_selected = True` |
| **`NO_SELECTION`** | Competitor offer chosen or no offer eligible. | `is_selected = False` |
| **`ORDER_CREATED`** | Razorpay Test-Mode order created via Phase 5 Execution Gate. | Requires `provider_order_id` |
| **`PAYMENT_SUCCESS`** | Payment verified via authoritative `payment.captured` webhook. | Requires `verified_payment_id` |
| **`PAYMENT_FAILURE`** | Payment failed or authorization expired. | Requires webhook failure status |
| **`EXECUTION_REJECTED`** | Execution gate rejected proposal on fresh inventory or margin checks. | Execution gate rejection |
| **`EXPERIMENT_INCONCLUSIVE`**| Observation derived from an inconclusive experiment arm. | Zero or sub-MDE delta |

### Mandatory Outcome Invariants:
$$\text{ORDER\_CREATED} \ne \text{PAYMENT\_SUCCESS}$$
$$\text{SIMULATED\_SELECTION} \ne \text{PAYMENT\_SUCCESS}$$

---

## 5. Economic Field Conventions

- **Money**: Expressed strictly in positive integer paise (`BigInteger`). Zero float arithmetic.
- **Percentages**: Stored as Decimal / float rounded to 2 decimal places (`ROUND_HALF_UP`).
- **Expected vs. Observed Separation**:
  - `expected_revenue_paise` & `expected_contribution_paise`: Populated for `SIMULATED` outcomes.
  - `observed_revenue_paise` & `observed_contribution_paise`: Populated strictly for `TEST_MODE_OBSERVED` outcomes with `PAYMENT_SUCCESS`.
