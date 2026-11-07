# Phase 8.4 Learning Algorithm Specification: Contextual Linear UCB

**Contract**: `learning-algorithm/v1`  
**Feature Schema**: `feature-schema/v1` (19 dimensions)  
**Model State Contract**: `learning-model/v1`  
**Status**: **COMPLETE, VERIFIED, ADVERSARIALLY HARDENED, CONTRACT FROZEN**  
**Core Invariant**: **PREDICTIVE DECISION SUPPORT ONLY; ZERO AUTONOMOUS PROMOTION, ZERO EXPLORATION POLICIES, ZERO POLICY MUTATION, ZERO EXECUTION CALLS**

---

## 1. Why Contextual Linear UCB Was Selected

Contextual Linear Upper Confidence Bound (LinUCB) was selected as the foundational learning algorithm for the Merchant Policy Agent because the domain possesses:
1. **Structured Buyer Context**: Intent category, budget tiers, quantity, and requirements are structured and known prior to policy selection.
2. **Structured Policy Representation**: Candidate policies exhibit structured strategies, discount tiers, bundle configurations, and economic attributes.
3. **Continuous Signed Reward**: Verified merchant contribution (Phase 8.2) is a continuous monetary quantity that can be positive, zero, or negative.
4. **Sparse Historical Evidence**: Individual merchants experience sparse, high-stakes commercial interactions. Deep RL (PPO, DQN) or black-box neural networks requires millions of samples, is sample-inefficient, and suffers from catastrophic forgetting.
5. **Need for Transparent Uncertainty**: LinUCB provides an explicit, closed-form uncertainty metric ($\sqrt{x^T A^{-1} x}$) derived from the curvature of observed feature coverage.
6. **Deterministic & Auditable**: State updates are linear and rank-1; replaying history guarantees bitwise identical models.

---

## 2. Problem Formulation & Objective Target

Given:
- A specific merchant $m$
- A pre-decision commercial context vector $c$ (from buyer intent)
- A candidate commercial policy proposal $p$ (from Phase 4 candidate generation)

The model estimates the expected merchant economic contribution:
$$\mathbb{E}[R \mid x] \approx x^T \theta^*$$
where $x = \phi(c, p) \in \mathbb{R}^{19}$ is the joint pre-decision feature vector, and $R$ is the verified net merchant contribution inherited from Phase 8.2 (`merchant-reward/v1`, `contribution-formula/v1`).

---

## 3. Mathematical Formulation

### Sufficient Statistics:
The model maintains:
$$A = \lambda I_{19} + \sum_{i=1}^N x_i x_i^T \in \mathbb{R}^{19 \times 19}$$
$$b = \sum_{i=1}^N x_i r_i \in \mathbb{R}^{19}$$
where:
- $\lambda > 0$ is the $L_2$ ridge regularization parameter (default $\lambda = 1.0$).
- $x_i \in \mathbb{R}^{19}$ is the normalized feature vector for observation $i$.
- $r_i$ is the observed reward in model units ($r_i = \text{contribution\_paise} / 100.0$).

### Parameter Estimation:
$$\hat{\theta} = A^{-1} b$$
Solved via Cholesky decomposition $A = L L^T$:
1. $L w = b \implies w$ (Forward substitution)
2. $L^T \hat{\theta} = w \implies \hat{\theta}$ (Backward substitution)

### Prediction & Uncertainty:
1. **Predicted Contribution**:
   $$\hat{R}(x) = \text{round}\left((x^T \hat{\theta}) \times 100\right) \quad [\text{in integer paise}]$$
2. **Uncertainty Diagnostic**:
   $$\sigma(x) = \sqrt{x^T A^{-1} x} = \|L^{-1} x\|_2$$
   Computed by solving $L y = x$ via forward substitution, yielding $\sigma(x) = \sqrt{\sum y_i^2}$.
3. **Upper Confidence Bound (Diagnostic Metric Only)**:
   $$\text{UCB}(x) = \hat{R}(x) + \text{round}(\alpha \cdot \sigma(x))$$
   where $\alpha \ge 0$ is the confidence multiplier (default $\alpha = 10,000$ paise = ₹100).

---

## 4. Cold-Start Behavior

For a merchant with no prior observations ($N = 0$):
- $A = \lambda I_{19}$
- $b = \mathbf{0}_{19}$
- $\hat{\theta} = \mathbf{0}_{19}$
- $\hat{R}(x) = 0$ paise
- $\sigma(x) = \frac{1}{\sqrt{\lambda}} \|x\|_2$ (High initial uncertainty)
- $\text{UCB}(x) = \text{round}\left(\alpha \cdot \frac{\|x\|_2}{\sqrt{\lambda}}\right)$

The model does **not** invent merchant performance, nor does it automatically execute exploratory policies.

---

## 5. Non-Destructive Replay & Canonical Cutoff Ordering

The model supports deterministic batch rebuilds from Phase 8.3 historical memory:
1. **Current-Effective Invariant**: Queries only records with `is_current == True` and `learning_eligible == True`. Superseded records are excluded, eliminating double counting.
2. **Canonical Ordering**: Observations are processed in strict chronological order:
   $$\text{ORDER BY } \text{observed\_at ASC}, \text{id ASC}$$
3. **Temporal Cutoff ($T$)**: Rebuilds strictly filter $\text{observed\_at} \le T$, preventing future information leakage into historical evaluation.
4. **Determinism Guarantee**: Batch rebuild produces identical matrix states $A$, $b$, and $\hat{\theta}$ to sequential online updates.

---

## 6. Persistence & Concurrency Model

1. **Relational Table**: Persisted in `policy_learning_model_states` in PostgreSQL / SQLite.
2. **Sufficient Statistics Storage**: Serialized as native JSON arrays (`matrix_a_json`, `vector_b_json`, `theta_json`).
3. **Optimistic Locking**:
   - Every state record contains an integer `version` column.
   - Updates execute:
     ```sql
     UPDATE policy_learning_model_states
     SET matrix_a_json = :a, vector_b_json = :b, theta_json = :theta,
         observation_count = :count, version = version + 1
     WHERE merchant_id = :mid AND version = :expected_version;
     ```
   - If rowcount is 0, `ConcurrentModelUpdateError` is raised, preventing silent lost updates.

---

## 7. Merchant Isolation Guarantee

Models are strictly partitioned by `merchant_id`:
- Model A belongs solely to Merchant A.
- Model B belongs solely to Merchant B.
- Zero cross-tenant data sharing or pooling occurs.

---

## 8. Hard Boundary: What Phase 8.4 Does NOT Do

| Forbidden Action | Enforcing Layer | Phase Responsible |
|:---|:---:|:---:|
| Policy candidate selection | Firewall | Phase 8.5 |
| Exploration vs. exploitation decisions | Firewall | Phase 8.7 |
| Policy promotion / deployment | Firewall | Phase 8.6 |
| Policy mutation / parameter tuning | Firewall | Phase 8.8 |
| Razorpay transaction execution | Commercial Gate | Phase 5 |
| Causal uplift claims | Statistical firewall | Controlled Experiments (Phase 7) |

---

## 9. Handoff to Phase 8.5

Phase 8.4 exposes:
```json
{
  "merchant_id": "merch_atlas",
  "policy_id": "p_bundle_treat",
  "policy_version": "merchant-policy/v1",
  "buyer_context_key": "bck_travel_mid",
  "predicted_contribution_paise": 175000,
  "uncertainty": 0.421,
  "ucb_score_paise": 217100,
  "observation_count": 14,
  "model_version": "learning-model/v1",
  "algorithm_version": "learning-algorithm/v1",
  "feature_version": "feature-schema/v1"
}
```

Phase 8.5 will consume these predictive diagnostics to implement formal candidate-selection semantics.
