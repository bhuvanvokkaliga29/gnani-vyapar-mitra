# Phase 7 Contract: Controlled Policy Experiments

**Specification Version**: `policy-experiment/v1`  
**Result Version**: `experiment-result/v1`  
**Observation Version**: `experiment-observation/v1`  
**Status**: ACTIVE & CONTRACT FROZEN  

---

## 1. Architectural Role & Boundary

The Controlled Policy Experiment framework tests whether changes in commercial policy measurably change AI-buyer selection and transaction outcomes under controlled, reproducible conditions.

```text
PolicyProposal (Control)    PolicyProposal (Treatment)
          │                               │
          └───────────────┬───────────────┘
                          │
                   PolicyDiffEngine
                          │
                 PolicyExperiment v1
                          │
                 AssignmentEngine
              (SHA-256 Seeded Hash)
                          │
        ┌─────────────────┴─────────────────┐
        ▼                                   ▼
Control Arm (Assigned)              Treatment Arm (Assigned)
[Approx. Balanced Allocation]       [Approx. Balanced Allocation]
        │                                   │
        ├─────────────────┬─────────────────┤
        ▼                                   ▼
AI Buyer Lab (Phase 6)              AI Buyer Lab (Phase 6)
        │                                   │
[If Selected & Test Mode Enabled]   [If Selected & Test Mode Enabled]
Execute Assigned Variant            Execute Assigned Variant
(via Phase 5 Execution Gate)        (via Phase 5 Execution Gate)
        │                                   │
Razorpay Test Mode Order            Razorpay Test Mode Order
        │                                   │
        └─────────────────┬─────────────────┘
                          │
                ExperimentMetricEngine
               (Deterministic Formulas)
                          │
                ExperimentEvaluator
    (Effect Size + Sample Size + Uncertainty/MDE + Guardrails)
                          │
                          ▼
                ExperimentResult v1
```

### Inviolable Boundaries:
- **No Automatic Policy Learning**: Experiment results provide empirical evidence for Phase 8; they **never** mutate merchant policies or bandit weights automatically.
- **No Direct Razorpay Calls**: Any Test-Mode order execution must strictly traverse Phase 5 `ExecutionGate`.
- **Assigned Variant Execution**: The system executes the **assigned variant** for that decision instance when selected by the buyer, never "winning variants" before evaluation is complete.
- **Controlled Comparison vs Causal Claims**: Controlled randomized comparison over simulated scenarios establishes relative empirical performance under test conditions; it does not claim unconditional real-world causal certainty.
- **N8N Decision**: Explicitly omitted. The Python application is the authoritative source of truth for assignments, metrics, and state.

---

## 2. PolicyExperiment Contract (`policy-experiment/v1`)

```json
{
  "experiment_id": "exp_4b2c7e189a01",
  "experiment_version": "policy-experiment/v1",
  "merchant_id": "merch_atlas_travel",
  "name": "Atlas Travel Pack Value Bundle vs Single Product",
  "status": "RUNNING",
  "control_policy_id": "prop_ctrl_atlas_single",
  "treatment_policy_id": "prop_treat_atlas_bundle",
  "control_proposal_snapshot": { ... },
  "treatment_proposal_snapshot": { ... },
  "policy_diff": {
    "control_strategy": "SINGLE_PRODUCT",
    "treatment_strategy": "VALUE_BUNDLE",
    "control_price_paise": 299900,
    "treatment_price_paise": 349900,
    "price_delta_paise": 50000,
    "control_margin_percent": 49.98,
    "treatment_margin_percent": 51.41,
    "margin_delta_percent": 1.43,
    "added_items": ["rain_cover"],
    "warranty_delta_months": 12,
    "summary": "Strategy: SINGLE_PRODUCT -> VALUE_BUNDLE; Price: +₹500.00; Added items: rain_cover; Warranty: +12 mo"
  },
  "hypothesis": {
    "population_description": "Budget-conscious laptop buyers requiring 15.6 inch compartment",
    "control_description": "Single backpack at ₹2,999 with 12 mo warranty",
    "treatment_description": "Value bundle with rain cover at ₹3,499 with 24 mo warranty",
    "expected_direction": "HIGHER",
    "primary_metric": "EXPECTED_CONTRIBUTION_PER_SHOPPER",
    "rationale": "Extended warranty and bundled rain cover improve utility and contribution per shopper",
    "guardrail_metrics": ["MIN_MARGIN_PERCENT"]
  },
  "primary_metric": "EXPECTED_CONTRIBUTION_PER_SHOPPER",
  "secondary_metrics": ["SELECTION_RATE", "AOV_PAISE", "MARGIN_PERCENT", "ORDER_CREATION_RATE"],
  "guardrails": [
    {
      "guardrail_type": "MIN_MARGIN_PERCENT",
      "threshold_value": 0.40,
      "description": "Minimum 40% margin floor"
    }
  ],
  "randomization_seed": 42,
  "assignment_strategy": "DETERMINISTIC_HASH",
  "population_scenarios": ["scen_01", "scen_02", "scen_03", ...],
  "sample_size_target": 50,
  "created_at": "2026-09-03T12:00:00Z",
  "created_by": "system"
}
```

---

## 3. Observation Contract (`experiment-observation/v1`)

```json
{
  "observation_id": "obs_9f8e7d6c5b4a",
  "experiment_id": "exp_4b2c7e189a01",
  "scenario_id": "scen_01",
  "variant": "TREATMENT",
  "outcome_type": "SIMULATED",
  "buyer_selection_result_id": "scen_01",
  "selected_offer_id": "off_cand_treat",
  "is_selected": true,
  "execution_id": null,
  "order_id": null,
  "razorpay_order_id": null,
  "payment_outcome": null,
  "revenue_paise": 349900,
  "contribution_paise": 179900,
  "margin_percent": 51.41,
  "guardrail_violations": [],
  "observed_at": "2026-09-03T12:05:00Z",
  "idempotency_key": "obs_exp_4b2c7e189a01_scen_01_TREATMENT"
}
```

---

## 4. Experiment Result Contract (`experiment-result/v1`)

```json
{
  "result_version": "experiment-result/v1",
  "experiment_id": "exp_4b2c7e189a01",
  "merchant_id": "merch_atlas_travel",
  "status": "COMPLETED",
  "evidence_status": "SUFFICIENT_EVIDENCE",
  "winner": "TREATMENT",
  "winner_rationale": "Treatment demonstrated superior EXPECTED_CONTRIBUTION_PER_SHOPPER (+28.4%) while satisfying all 1 experiment guardrails.",
  "sample_counts": {
    "CONTROL": 24,
    "TREATMENT": 26
  },
  "actual_control_count": 24,
  "actual_treatment_count": 26,
  "allocation_ratio": 1.083,
  "control_metrics": {
    "sample_size": 24,
    "selection_count": 12,
    "selection_rate": 0.48,
    "total_revenue_paise": 3598800,
    "aov_paise": 299900,
    "total_contribution_paise": 1798800,
    "expected_contribution_per_shopper_paise": 71952,
    "average_margin_percent": 49.98
  },
  "treatment_metrics": {
    "sample_size": 25,
    "selection_count": 16,
    "selection_rate": 0.64,
    "total_revenue_paise": 5598400,
    "aov_paise": 349900,
    "total_contribution_paise": 2878400,
    "expected_contribution_per_shopper_paise": 115136,
    "average_margin_percent": 51.41
  },
  "metric_deltas": {
    "EXPECTED_CONTRIBUTION_PER_SHOPPER": {
      "metric_name": "EXPECTED_CONTRIBUTION_PER_SHOPPER",
      "control_value": 71952.0,
      "treatment_value": 115136.0,
      "absolute_difference": 43184.0,
      "relative_difference_percent": 60.02,
      "directionally_improved": true
    },
    "SELECTION_RATE": {
      "metric_name": "SELECTION_RATE",
      "control_value": 0.48,
      "treatment_value": 0.64,
      "absolute_difference": 0.16,
      "relative_difference_percent": 33.33,
      "directionally_improved": true
    }
  },
  "guardrail_results": [
    {
      "guardrail_type": "MIN_MARGIN_PERCENT",
      "threshold_value": 40.0,
      "observed_value": 51.41,
      "passed": true,
      "detail": "Observed margin 51.4% meets floor 40.0%"
    }
  ]
}
```
