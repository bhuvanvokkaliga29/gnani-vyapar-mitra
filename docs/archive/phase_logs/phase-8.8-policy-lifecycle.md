# Phase 8.8 & 8.8.1 — Policy Promotion & Lifecycle Versioning

## Contract: `policy-lifecycle/v1` + `promotion-policy/v1`

## Overview

Phase 8.8 introduces the project's **first controlled policy-state mutation**: evidence-gated lifecycle management that promotes observed candidate policies to active merchant policies, and manages rollback to historical versions.

Phase 8.8.1 hardens the promotion gate against:
1. Observational selection bias
2. Insufficient evidence
3. Stale evidence & temporal drift
4. Inconsistent evidence populations
5. Stale safety state
6. Promotion based solely on model prediction, UCB scores, or exploration exposure

### Inviolable Core Principles

```
PREDICTION ≠ PROMOTION
UCB ≠ PROMOTION
EXPLORATION SUCCESS ≠ AUTOMATIC PROMOTION
PAYMENT SUCCESS ≠ AUTOMATIC PROMOTION
POSITIVE REVENUE ≠ AUTOMATIC PROMOTION
```

**Conservative Default**: If evidence is insufficient, conflicting, stale, or safety is unverified, **DO NOT PROMOTE**. The existing active policy remains completely unchanged.

---

## Evidence-Strength Hierarchy

| Evidence Level | Type | Source | Guarantees & Constraints |
|---|---|---|---|
| **Level 1 (Highest)** | `CONTROLLED_EXPERIMENT` | Phase 7 Controlled A/B Experiment | Grounded in randomized/deterministic hash assignment. Verifies candidate is treatment arm, treatment won, evidence is `SUFFICIENT_EVIDENCE`, guardrails passed, and Phase 8.6 fresh safety passes. |
| **Level 2 (Conservative)** | `OBSERVATIONAL_HISTORY` | Phase 8.3 Historical Policy Memory | Subject to historical selection bias. Requires non-domination (max 50% contribution share per opportunity), context diversity, recency window compliance, outperforming `NO_OFFER`, zero historical safety breaches, and attaches an explicit non-causal disclaimer. |

### Selection-Bias Discipline & Statistical Claims
The implementation explicitly forbids claiming:
- Causal superiority or guaranteed uplift on observational evidence.
- Every observational promotion result attaches the disclaimer:
  > *"Observational evidence only. Subject to historical selection bias. Does not establish causal superiority or guaranteed uplift."*

---

## Lifecycle State Machine

```
                  CANDIDATE (Proposed from Phase 4)
                      │
                      │ Evidence thresholds met
                      │ AND Fresh Phase 8.6 safety passes
                      ▼
            ELIGIBLE_FOR_PROMOTION
                      │
                      │ Atomic promotion transaction
                      ▼
                   ACTIVE (Exactly 1 per merchant)
                  /      \
  Superseded by  /        \  Explicit rollback
  new promotion /          \ (Fresh 8.6 required)
               ▼            ▼
            RETIRED     ROLLED_BACK
               │
               │ Re-activated via rollback
               └──────► ACTIVE
```

---

## Population & Version Integrity

1. **Strict Version Matching**: Observations are scoped to exact `(merchant_id, policy_id, policy_version)`. Evidence from version `v1` cannot authorize version `v2`.
2. **Current-Effective Only**: Superseded observations (`is_current = False` or `superseded_by is not None`) are strictly excluded.
3. **Deduplication**: Multi-recorded opportunities are deduplicated so no opportunity contributes twice.
4. **Temporal Recency**: Observations older than `recency_window_days` (default 30 days) are excluded as stale. If historical evidence exists but is stale, fails with `STALE_EVIDENCE`.
5. **Future Evidence Rejection**: Observations with `observed_at > evaluation_time` are rejected (`FUTURE_EVIDENCE_REJECTED`).

---

## Database Models

### `MerchantActivePolicy`
- **Purpose**: Single-row-per-merchant pointer enforcing the active policy invariant.
- **Primary Key**: `merchant_id` (physically prevents duplicate active rows).
- **Concurrency**: `SELECT ... FOR UPDATE` row locking during promotion/rollback.

### `MerchantPolicyVersionRecord`
- **Purpose**: Immutable record of every policy version ever promoted.
- **Unique Constraint**: `(merchant_id, policy_id, policy_version)`.
- **Fields**: `strategy_type`, `product_ids_json`, `incentive_json`, `lifecycle_status`, `promoted_at`, `retired_at`, `rationale`.

### `PolicyLifecycleAuditRecord`
- **Purpose**: Append-only audit trail for all promotions, retirements, and rollbacks.
- **Fields**: `transition_type`, `previous_active_policy_id`, `resulting_active_policy_id`, `eligibility_status`, `failure_codes_json`, `evidence_type`, `evidence_references_json`, `safety_check_id`, `config_version`.

---

## Failure Taxonomy

| Code | Meaning |
|------|---------|
| `INSUFFICIENT_SAMPLE_SIZE` | Sample size below threshold |
| `NEGATIVE_CONTRIBUTION` | Observed mean contribution ≤ 0 paise |
| `NO_IMPROVEMENT_OVER_BASELINE` | Candidate does not outperform `NO_OFFER` baseline |
| `GUARDRAIL_BREACH` | Historical safety violation or experiment guardrail failure |
| `INCONCLUSIVE_EXPERIMENT` | Experiment not COMPLETED or evidence status INCONCLUSIVE |
| `EXPERIMENT_NOT_WON` | Treatment did not win experiment |
| `EXPERIMENT_NOT_FOUND` | Controlled experiment required but not found |
| `EXPERIMENT_TREATMENT_MISMATCH` | Candidate policy is not the treatment arm of the experiment |
| `SAFETY_GATE_REJECTED` | Fresh Phase 8.6 safety check returned REJECTED |
| `PREDECESSOR_MISMATCH` | Optimistic concurrency conflict |
| `CROSS_MERCHANT_FORBIDDEN` | Tenant isolation violation |
| `STALE_EVIDENCE` | Observations fall outside recency window |
| `FUTURE_EVIDENCE_REJECTED` | Observations timestamped in the future |
| `POLICY_VERSION_MISMATCH` | Observations found for policy_id do not match candidate version |
| `OBSERVATIONAL_CONCENTRATION_EXCEEDED` | Single opportunity accounts for > 50% of contribution |
| `INSUFFICIENT_CONTEXT_DIVERSITY` | Distinct buyer context count below required threshold |
| `OBSERVATIONAL_PROMOTION_DISALLOWED` | Observational promotion disabled or forbidden |

---

## Test Coverage

| Suite | Count | Status |
|-------|-------|--------|
| Unit (evaluator) | 18 | ✅ PASS |
| Integration (service) | 7 | ✅ PASS |
| Adversarial (invariants A–O + AST) | 12 | ✅ PASS |
| **Full Regression** | **596** | **✅ PASS, 0 regressions** |

---

## Execution Authority

Phase 8.8 & 8.8.1 has **ZERO** execution authority:
- Cannot create Razorpay orders
- Cannot capture payments
- Cannot reserve inventory
- Cannot update learning models (LinUCB weights)
- Cannot modify historical evidence records
- Contains no n8n tokens or workflow triggers
- Verified by static AST boundary audit
