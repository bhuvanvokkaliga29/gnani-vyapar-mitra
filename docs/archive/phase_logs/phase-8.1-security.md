# Phase 8.1 Security, Boundaries & Tenant Isolation

## 1. Threat Model & Untrusted Inputs

In commercial policy learning, untrusted clients, rogue agents, or compromised frontends might attempt to:
1. Inject fake rewards, fake conversions, or inflated contribution figures to manipulate future learning.
2. Force `learning_eligible = True` on unsafe or guardrail-violating evidence.
3. Access or attach learning evidence belonging to competing merchants (cross-tenant leakage).
4. Perform illicit customer surveillance by attaching demographic profiling (age, gender, income) to buyer contexts.
5. Silently promote simulated model expectations into verified transaction records.

---

## 2. Inviolable Security Boundaries

### Boundary 1: Zero Client-Supplied Evidence
- Clients and external API callers **cannot submit raw evidence payloads, custom rewards, or declare eligibility**.
- Evidence is ingested strictly by server-side processes from authoritative internal records:
  - Phase 7 `ExperimentRecord` and `ObservationRecord`
  - Phase 6 `BuyerSelectionResult`
  - Phase 5 `ExecutionRecord`
  - Phase 1 verified `payment.captured` webhooks.

### Boundary 2: Multi-Tenant Isolation
- All learning evidence queries enforce strict tenant scoping:
  ```python
  stmt = select(LearningEvidenceRecord).where(
      and_(
          LearningEvidenceRecord.id == evidence_id,
          LearningEvidenceRecord.merchant_id == authenticated_merchant_id
      )
  )
  ```
- Cross-tenant requests return HTTP 404 or raise `CrossTenantLearningError`.
- Verified by automated test: `test_tenant_isolation_cross_merchant_learning_access_denied`.

### Boundary 3: Rejection of Demographic Profiling
- The `BuyerContextKeyBuilder` inspects input intents against `FORBIDDEN_DEMOGRAPHIC_KEYS`.
- Any attempt to profile on age, gender, race, income, or health raises an immediate `SecurityBoundaryError`.
- Verified by automated test: `test_context_key_rejects_demographic_attributes`.

### Boundary 4: Static AST Boundary Audit (Zero Learning Algorithms in 8.1)
- Automated AST audit scans all files in `services/learning/` and asserts zero occurrences of:
  `bandit`, `q_learning`, `reinforcement_learning`, `reward_model`, `update_policy`, `RazorpayClient`, or `rzp_test`.
- Verified by automated test: `test_architectural_boundary_no_learning_algorithms_or_razorpay_in_learning`.

### Boundary 5: Passive Invariant (Zero Side-Effects)
- Creating and validating learning evidence is strictly passive.
- It causes **zero mutations** to merchant policies, product prices, discounts, inventory levels, or merchant priorities.
- Verified by automated test: `test_no_merchant_policy_mutation_side_effects`.
