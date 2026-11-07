# Phase 8.3 Contract: Merchant Policy Memory

**Contract Version**: `merchant-memory/v1`  
**Status**: ACTIVE & CONTRACT FROZEN  
**Role**: Authoritative persistence and retrieval layer for immutable historical policy evidence and verified rewards.

---

## 1. Architectural Boundary & Firewall

Phase 8.3 is a **persistence and retrieval layer**. It consumes the frozen outputs of Phase 8.1 (`PolicyLearningEvidence`) and Phase 8.2 (`PolicyOpportunityReward`, `AggregatedRewardObjective`) and stores them as immutable historical facts.

```text
Phase 8.1 Evidence (merchant-learning/v1)
                  ↓
Phase 8.2 Reward (merchant-reward/v1, contribution-formula/v1)
                  ↓
Phase 8.3 Policy Memory (merchant-memory/v1)
                  ↓
════════════════════════════════════════════════════════════════════════════
                     FIREWALL / HARD STOP BOUNDARY
   (Zero bandits, zero RL, zero policy updates, zero exploration/exploitation)
════════════════════════════════════════════════════════════════════════════
                  ↓
     [Deferred to Phase 8.4]: Autonomous Policy Learning Algorithm
```

---

## 2. PolicyMemoryRecord Contract (`merchant-memory/v1`)

```json
{
  "memory_id": "mem_4a7c1b8e9d20",
  "memory_version": "merchant-memory/v1",
  "merchant_id": "merch_atlas_travel",
  "opportunity_id": "exp_4b2c7e189a01:scen_01:TREATMENT",
  "buyer_context_key": "bck_travel_backpack_TIER_MID_2K_4K_7e3a9c4f12d0",
  "scenario_id": "scen_01",
  "policy_id": "prop_treat_atlas_bundle",
  "policy_version": "merchant-policy/v1",
  "experiment_id": "exp_4b2c7e189a01",
  "experiment_version": "policy-experiment/v1",
  "variant": "TREATMENT",
  "evidence_id": "evi_8f7b2c9a1d3e",
  "evidence_source": "TEST_MODE_OBSERVED",
  "outcome_type": "PAYMENT_SUCCESS",
  "learning_eligible": true,
  "reward_id": "rwd_7a1b3c5e8f9d",
  "reward_version": "merchant-reward/v1",
  "formula_version": "contribution-formula/v1",
  "reward_state": "REWARD_ELIGIBLE",
  "is_admissible": true,
  "is_safety_violation": false,
  "realized_revenue_paise": 349900,
  "realized_cogs_paise": 170000,
  "realized_discount_paise": 0,
  "reward_contribution_paise": 179900,
  "margin_percent": 51.41,
  "is_current": true,
  "superseded_by": null,
  "supersedes": "mem_previous_01",
  "correction_reason": "RECONCILIATION_PAYMENT_CAPTURED",
  "reconciliation_ref": "evt_pay_captured_123",
  "idempotency_key": "mem_evi_8f7b2c9a1d3e",
  "observed_at": "2026-09-03T13:00:00Z",
  "persisted_at": "2026-09-03T13:05:00Z"
}
```

---

## 3. Database Schema & Indexing

Stored in the `policy_memory` table in PostgreSQL / SQLite:

| Column | Type | Constraints | Description |
|:---|:---|:---|:---|
| `id` | `String(64)` | PK | `mem_...` |
| `memory_version` | `String(32)` | NOT NULL | `merchant-memory/v1` |
| `merchant_id` | `String(64)` | FK -> `merchants.id` | Tenant isolation scope |
| `opportunity_id` | `String(128)` | NOT NULL | Canonical decision instance ID |
| `buyer_context_key` | `String(128)` | NOT NULL | Deterministic intent fingerprint |
| `scenario_id` | `String(64)` | NOT NULL | Benchmark scenario ID |
| `policy_id` | `String(64)` | NOT NULL | Target policy ID |
| `policy_version` | `String(32)` | NOT NULL | Immutable policy version |
| `experiment_id` | `String(64)` | FK -> `experiments.id` | Experiment ID |
| `variant` | `String(16)` | NOT NULL | `CONTROL` or `TREATMENT` |
| `evidence_id` | `String(64)` | FK -> `learning_evidence.id` | Upstream evidence link |
| `evidence_source` | `String(32)` | NOT NULL | `SIMULATED` / `TEST_MODE_OBSERVED` |
| `outcome_type` | `String(32)` | NOT NULL | Outcome type |
| `learning_eligible` | `Boolean` | NOT NULL | Firewall eligibility |
| `reward_id` | `String(64)` | NOT NULL | Upstream reward link |
| `reward_state` | `String(32)` | NOT NULL | Reward taxonomy state |
| `is_admissible` | `Boolean` | NOT NULL | Population admissibility |
| `is_safety_violation`| `Boolean` | NOT NULL | Commercial guardrail failure flag |
| `realized_revenue_paise` | `BigInteger` | NOT NULL | Net revenue in paise |
| `realized_cogs_paise` | `BigInteger` | NOT NULL | COGS in paise |
| `reward_contribution_paise` | `BigInteger` | NOT NULL | Net modeled contribution in paise |
| `margin_percent` | `Numeric(5, 2)` | NOT NULL | Gross profit margin % |
| `is_current` | `Boolean` | NOT NULL | True if authoritative current effective state |
| `superseded_by` | `String(64)` | NULLABLE | Memory ID of replacing record |
| `supersedes` | `String(64)` | NULLABLE | Memory ID of replaced record |
| `correction_reason` | `String(128)` | NULLABLE | Reconciliation / correction reason |
| `reconciliation_ref` | `String(128)` | NULLABLE | Upstream transaction / webhook ref |
| `idempotency_key` | `String(128)` | UNIQUE, NOT NULL | `mem_{evidence_id}` deduplication |
| `observed_at` | `DateTime` | NOT NULL | Observation timestamp |
| `persisted_at` | `DateTime` | NOT NULL | Persistence timestamp |

### Dedicated Indexes:
- `ix_policy_memory_merchant_policy`: `(merchant_id, policy_id)`
- `ix_policy_memory_merchant_policy_ver`: `(merchant_id, policy_id, policy_version)`
- `ix_policy_memory_merchant_context`: `(merchant_id, buyer_context_key)`
- `ix_policy_memory_merchant_pol_ctx`: `(merchant_id, policy_id, buyer_context_key)`
- `ix_policy_memory_merchant_exp`: `(merchant_id, experiment_id)`
- `ix_policy_memory_merchant_obs_time`: `(merchant_id, observed_at)`
- `ix_policy_memory_merchant_opp_current`: `(merchant_id, opportunity_id, is_current)`

---

## 4. Immutability & Deduplication Rules

1. **Append-Only Immutability**: Historical records are never silently updated or overwritten. Stored historical facts retain the exact policy version, reward version, and formula version that existed when the observation occurred.
2. **Deterministic Deduplication**: Database unique constraint on `idempotency_key = f"mem_{evidence.evidence_id}"` ensures that replaying an observation returns the existing record without duplicating storage.
