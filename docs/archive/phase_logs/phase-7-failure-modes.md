# Phase 7 Failure Modes & Edge Case Handling

## 1. Statistical & Evidence Failures

### A. Insufficient Sample Size (`INSUFFICIENT_SAMPLE`)
- **Trigger**: Total observations across Control and Treatment are below the minimum threshold ($N < 10$) or either arm has 0 observations.
- **Handling**:
  - `evidence_status`: `INSUFFICIENT_SAMPLE`
  - `winner`: `None`
  - `winner_rationale`: Transparently states that sample size is too small to establish a statistically reliable comparison.
  - The system refuses to manufacture certainty.

### B. Inconclusive / Noise Comparison (`INCONCLUSIVE`)
- **Triggers**:
  1. **Zero Delta**: Absolute difference in primary metric between Treatment and Control is zero.
  2. **Sub-MDE Effect Size**: The relative difference is below the minimum detectable effect threshold (e.g. Control = 50.0%, Treatment = 50.1%, relative lift = 0.2% $< 2.0\%$ MDE).
- **Handling**:
  - `evidence_status`: `INCONCLUSIVE`
  - `winner`: `None`
  - `winner_rationale`: Explicitly documents that the observed effect size is within the uncertainty / sampling noise threshold.

---

## 2. Guardrail Breach Handling (`GUARDRAIL_FAILURE`)

- **Trigger**: Treatment improves primary metric (e.g. higher selection rate) but breaches a merchant constraint (e.g. margin falls to 25% below 40% floor).
- **Handling**:
  - `evidence_status`: `GUARDRAIL_FAILURE`
  - `winner`: `CONTROL`
  - `winner_rationale`: Explicitly documents that Treatment is disqualified due to constraint violation and Control is retained as the safe baseline.

---

## 3. Premature Winner Bias Defense (Assigned Variant Execution)

- **Vulnerability**: Executing a "winning variant" before the experiment has completed introduces severe selection bias and invalidates the test.
- **Defense**:
  - The system executes the **assigned variant** for each individual shopper decision instance when selected by the buyer.
  - Winner declaration is strictly performed **post-hoc** by `ExperimentEvaluator` after all observations have been collected.

---

## 4. Observation Idempotency & Duplicate Delivery

- **Trigger**: Duplicate observation submission or repeated execution requests for the same `(experiment_id, scenario_id, variant)`.
- **Handling**:
  - Controlled by deterministic `idempotency_key = f"obs_{experiment_id}_{scenario_id}_{variant}"`.
  - Stored in SQLite/PostgreSQL with `unique=True`.
  - Duplicate attempts return the existing cached observation without double-counting revenue, contribution, or sample size.

---

## 5. Outcome Integrity: Order Creation vs. Payment Capture

- **Mandatory Invariant**:
  $$\text{ORDER\_CREATED} \ne \text{PAID}$$
- An order created via Phase 5 Execution Gate is initially marked `payment_outcome = 'PENDING'`.
- Payment success is **only** recorded when verified by an authoritative `payment.captured` webhook from Razorpay.
- Duplicate or out-of-order webhook delivery is resolved by event deduplication in Phase 1 `WebhookService`.
