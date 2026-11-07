# Phase 7 Experiment Design: Controlled Policy Experimentation Methodology

## 1. Core Experimental Objective

The framework answers:
> **When the merchant changes its commercial policy, does that policy measurably change AI-buyer selection and/or transaction outcomes under a controlled test?**

To establish a defensible, controlled comparison, the experiment fixes all market fixtures, competitor offers, buyer requirements, and evaluation steps so that **the isolated policy difference is the only variable that differs** between the two arms.

---

## 2. Experimental Unit and Population Definition

- **Experimental Unit**: The individual **buyer decision instance / scenario opportunity**.
- **Controlled Population**: Defined by structured input characteristics (`BuyerIntent` specifications, budget bounds, required laptop size, and market competitor fixtures).
- **Interference & Non-Contamination**:
  - Zero cross-contamination: A decision instance assigned to Control receives strictly Control offer attributes.
  - Treatment incentives, bundle accessories, and warranties never leak into Control.
  - Merchant internal metrics (COGS, target margins) are strictly hidden from the buyer choice layer.
- **Zero Demographic Profiling**: The population does not infer or rely on human personal traits (age, gender, income, geography).

---

## 3. Assignment Engine: Deterministic Cryptographic Allocation

Allocation is achieved via deterministic SHA-256 hashing:
```python
key = f"{experiment_id}:{scenario_id}:{randomization_seed}".encode("utf-8")
hash_digest = hashlib.sha256(key).hexdigest()
variant = VariantType.TREATMENT if (int(hash_digest[:8], 16) % 2 == 1) else VariantType.CONTROL
```

### Actual Allocation Reporting (Approximate Balance):
A hash split over a finite sample size does not guarantee an exact 50.00% / 50.00% split (e.g. 24 vs 26 out of 50). The framework explicitly records:
- `actual_control_count`: Number of decision instances assigned to Control.
- `actual_treatment_count`: Number of decision instances assigned to Treatment.
- `allocation_ratio`: The observed ratio ($\frac{\text{treatment\_count}}{\text{control\_count}}$).

---

## 4. Execution Flow: Assigned Variant Execution Without Selection Bias

During the experiment, the system executes the **assigned variant** for that individual decision instance, avoiding premature winner selection bias:

```text
Experiment Assignment (Scenario / Shopper)
       │
       ▼
Assigned Arm (Control OR Treatment)
       │
       ▼
AI Buyer Choice (Phase 6 Simulator)
       │
 [If Selected & Test Mode Enabled]
       ▼
Phase 5 Execution Gate (Execute Assigned Variant)
       │
       ▼
Observed Outcome (Order / Payment State)
       │
       ▼
Record Experiment Observation
       │
       ▼
Aggregate Metrics & Evaluate Winner (ExperimentEvaluator)
```

---

## 5. Minimal Change Principle & Policy Diff

An experiment is most informative when it isolates a minimal, observable policy change rather than simultaneously modifying 5 unrelated variables.

The `PolicyDiffEngine` generates an explicit structural and financial diff:
- Strategy type transition (e.g. `SINGLE_PRODUCT` $\to$ `VALUE_BUNDLE`)
- Price delta in minor units (`price_delta_paise`)
- Included accessory additions (`added_items`)
- Warranty duration delta (`warranty_delta_months`)
- Incentive additions (`treatment_incentives`)
- Gross margin delta (`margin_delta_percent`)

---

## 6. Controlled Comparison vs. Causal Claims

> [!NOTE]
> **Controlled Comparison $\ne$ Unconditional Real-World Causality**
> While SHA-256 allocation and controlled environments eliminate confounding factors in the simulation, real-world customer behavior introduces external factors (macroeconomics, advertising, channel effects). Phase 7 establishes **controlled empirical comparison** under defined conditions, not universal causal certainty.

---

## 7. Experiment Lifecycle State Machine

```text
DRAFT
  │ (Pre-flight validation: tenant check, candidate check, hypothesis check)
  ▼
VALIDATED
  │ (Ready to assign population)
  ▼
READY
  │ (Simulation / execution started)
  ▼
RUNNING
  │ (All observations recorded and evaluated)
  ▼
COMPLETED
```

### Evidence Classification Outcomes:
- `CONTROL`: Control outperformed Treatment by $>$ MDE, OR Treatment breached guardrails.
- `TREATMENT`: Treatment outperformed Control by $>$ MDE AND passed all guardrails.
- `INCONCLUSIVE`: Delta is zero OR effect size is within uncertainty / MDE threshold.
- `INSUFFICIENT_SAMPLE`: Total sample size $< 10$ or an arm has 0 observations.
- `GUARDRAIL_FAILURE`: Treatment breached margin floor or other constraints $\to$ Control retained.
