# Phase 7 Security & Boundary Architecture

## 1. Threat Model & Untrusted Inputs

In controlled policy experimentation, untrusted clients, malicious merchants, or flawed LLM suggestions might attempt to:
1. Fabricate experiment results (fake conversion, fake revenue, fake winners).
2. Bypass financial revalidation gates and call Razorpay directly.
3. Access or mutate experiments belonging to competing merchants (cross-tenant leakage).
4. Automatically mutate merchant policies or bandit weights without human or governance authorization.

---

## 2. Inviolable Security Boundaries

### Boundary 1: Zero Direct Razorpay Access
- `services/experiments/` contains **zero Razorpay clients, credentials, or direct API calls**.
- All Test Mode executions must strictly traverse the Phase 5 **Deterministic Commercial Execution Gate** (`POST /api/v1/policy/execute`), ensuring fresh inventory verification, margin floors, and single-use idempotency.
- Verified by automated AST audit: `test_architectural_boundary_no_direct_razorpay_in_experiments`.

### Boundary 2: Multi-Tenant Isolation
- All database queries and operations enforce `ExperimentRecord.merchant_id == merchant_id`.
- Merchant B cannot view, start, run, or observe Merchant A's experiments.
- Cross-tenant requests fail with HTTP 404 or `CrossTenantViolationError`.
- Verified by `test_tenant_isolation_cross_merchant_access_denied`.

### Boundary 3: Rejection of Client Tampering
- Clients cannot submit arbitrary revenue figures, conversion flags, or declare winners.
- All metrics are calculated deterministically by `ExperimentMetricEngine` from auditable observation records.
- Schema extra fields are strictly forbidden (`extra="forbid"`).

### Boundary 4: No Automatic Policy Learning Invariant
- Phase 7 is strictly an **empirical measurement system**.
- Completing an experiment generates an `ExperimentResult` containing evidence.
- It **does not**:
  - Update merchant catalog prices.
  - Update merchant margins.
  - Update merchant priorities.
  - Train multi-armed bandits.
  - Execute reinforcement learning.
- Verified by `test_no_automatic_policy_learning_invariant`.
