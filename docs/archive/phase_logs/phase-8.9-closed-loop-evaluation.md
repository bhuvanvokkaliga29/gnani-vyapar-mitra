# Phase 8.9 Closed-Loop Learning Evaluation
## Merchant Policy Agent — Razorpay AI Buildathon 2026, Track 01

### 1. Purpose & Architectural Objective
Phase 8.9 is the concluding sub-phase of Phase 8. It implements an authoritative, reproducible, and verifiable evaluation framework to test whether the existing Merchant Policy Agent architecture demonstrates true closed-loop learning across the complete observe $\to$ decide $\to$ act $\to$ measure $\to$ learn cycle.

The evaluated loop exercises:
$$\text{Buyer Intent} \longrightarrow \text{Commerce Context} \longrightarrow \text{Candidate Generation} \longrightarrow \text{Learned Prediction} \longrightarrow \text{Candidate Selection} \longrightarrow \text{Exploration/Exploitation} \longrightarrow \text{Safety Gate} \longrightarrow \text{Execution Gate (Test Mode)} \longrightarrow \text{Outcome} \longrightarrow \text{Evidence} \longrightarrow \text{Reward} \longrightarrow \text{Policy Memory} \longrightarrow \text{Model Update} \longrightarrow \text{Holdout Generalization}$$

---

### 2. Frozen Contract: `closed-loop-evaluation/v1`
An immutable schema envelope representing a complete evaluation run:
- **`evaluation_id`**: Unique string identifier (`eval_...`).
- **`merchant_id`**: Multi-tenant scoping identifier.
- **`mode`**: `SIMULATION`, `CONTROLLED_TEST_MODE`, or `REPLAY`.
- **`status`**: `RUNNING`, `COMPLETED`, `FAILED`.
- **`overall_outcome`**: `PASS`, `FAIL`, `INCONCLUSIVE`, `INSUFFICIENT_EVIDENCE`.
- **`baseline_definition`**: Grounded on `CANONICAL_BASELINE_POLICY_ID` (`cand_base_no_offer`, NO_OFFER).
- **`training_definition`**: Partition specification for sequential learning.
- **`evaluation_definition`**: Partition specification for pre-update scoring.
- **`holdout_definition`**: Partition specification for unseen generalization evaluation.
- **`summary_metrics`**: Aggregate quantitative performance indicators.
- **`learning_curve`**: Sequential snapshots across progress intervals (0%, 25%, 50%, 75%, 100%).
- **`holdout_metrics`**: Generalization metrics under frozen weights.
- **`diagnostics`**: Invariant verifications confirming architectural compliance.

---

### 3. Evaluation Modalities
1. **`SIMULATION`**:
   - Executes synthetic merchant catalog data evaluated against the deterministic AI Buyer Lab (`BuyerSimulator`).
   - Verifies learning mechanics, contextual feature updates, and candidate prioritization.
   - Strictly zero real-money commerce.
2. **`CONTROLLED_TEST_MODE`**:
   - Executes through the existing Phase 5 `ExecutionGate` and Phase 1 Razorpay Test Mode integration.
   - Authoritative transaction and webhook reconciliation.
   - Explicitly tagged as Test Mode; never described as real-money commerce.
3. **`REPLAY`**:
   - Replays previously captured observations from Phase 8.3 memory without creating new transactions or mutating live state.

---

### 4. Inviolable Population & Temporal Separation (Zero Leakage)
- **Pre-Update Scoring**: For every training opportunity, evaluation scoring occurs **BEFORE** the model is updated on that observation. Scoring an outcome after updating on it is strictly prohibited.
- **Frozen Holdout**: Once training completes, the model weights, memory records, and policy lifecycle are **STRICTLY FROZEN**. Holdout opportunities are scored purely to evaluate out-of-sample generalization. Holdout evaluation consumes zero learning budget and creates zero memory records.

---

### 5. Primary Metric: Expected Contribution per AI Shopper (ECPS)
- Computed in integer paise:
  $$\text{ECPS} = \frac{\sum_{i=1}^N \text{realized\_contribution\_paise}_i}{N}$$
- Zero-contribution trials (non-selections, non-conversions) are retained in the denominator.
- Negative contributions (loss leaders, below-COGS sales) are retained and pull down the mean.
- Deltas reported:
  - $\text{Absolute Delta} = \text{Learned ECPS} - \text{Baseline ECPS}$
  - $\text{Relative Delta} = \frac{\text{Learned ECPS} - \text{Baseline ECPS}}{\text{Baseline ECPS}} \times 100\%$ (when Baseline > 0)

---

### 6. Invariant Guarantees
- **Tenant Isolation**: Cross-tenant data access is blocked at schema, service, and database query layers.
- **Determinism**: Given an identical seed and dataset, runs reproduce bit-for-bit identical decisions and metrics.
- **Failure Resilience**: Margin floor violations, inventory shortages, or expired budgets deterministically trigger safety fallbacks without corrupting learning parameters.
- **Semantic Cleanliness**: Prohibits equating simulation to real transactions, selection to purchase, or correlation to causal claims.
