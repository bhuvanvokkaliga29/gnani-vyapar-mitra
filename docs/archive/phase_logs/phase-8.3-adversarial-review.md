# Phase 8.3 Adversarial Review: 25 Historical Memory Failure Modes

The Phase 8.3 Policy Memory and Historical Retrieval layer was subjected to a comprehensive adversarial evaluation across 25 distinct failure modes. All cases pass deterministically in [`tests/integration/test_memory_adversarial.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/integration/test_memory_adversarial.py).

---

## Adversarial Evaluation Matrix

| # | Failure Mode | Test Description | Deterministic System Behavior |
|:---:|:---|:---|:---|
| **1** | **Same context, different opportunities** | Two shoppers with identical commercial intent. | Unique `opportunity_id`s preserved; both records stored in memory. |
| **2** | **Same opportunity, duplicate observation** | Observation replayed with identical evidence ID. | Deduplicated via `idempotency_key = mem_{evidence_id}`; returns existing record. |
| **3** | **Retry of same write** | Exact write operation retried concurrently or sequentially. | Idempotent return of existing memory record without duplicate DB row. |
| **4** | **Same policy, multiple versions** | Policy v1 and v2 evaluated over time. | Immutable version history preserved: v1 and v2 stored separately. |
| **5** | **Same context across policies** | Context evaluated under Policy A and Policy B. | Orthogonal storage: both policies' performance in that context recorded. |
| **6** | **Same policy across contexts** | Policy evaluated under Backpack and Duffel contexts. | Context fingerprints recorded separately without cross-contamination. |
| **7** | **Merchant A reading Merchant B history** | Cross-tenant access attempted via query or ID fetch. | Strictly rejected with `MemoryTenantViolationError` / `403 Forbidden`. |
| **8** | **Simulated evidence preserved** | Simulation benchmark evidence ingested. | Stored with `evidence_source = SIMULATED`. |
| **9** | **Test Mode observed evidence preserved** | Real Razorpay test-mode transaction evidence ingested. | Stored with `evidence_source = TEST_MODE_OBSERVED`. |
| **10** | **Invalid evidence preserved** | Corrupted evidence record ingested. | Stored with `reward_state = REWARD_INVALID` and `is_admissible = False`. |
| **11** | **Guardrail violation preserved** | Commercial guardrail failure ingested. | Stored with `reward_state = REWARD_GUARDRAIL_VIOLATION`, `is_safety_violation = True`, and contribution = 0. |
| **12** | **Zero contribution preserved** | Eligible non-purchase ingested. | Stored with `reward_state = REWARD_ZERO` and contribution = 0 paise. |
| **13** | **Negative contribution preserved** | Loss-leader selling below COGS. | Negative contribution (-₹200) strictly preserved as negative integer paise. |
| **14** | **Missing reward rejected** | Upstream evidence evaluation failure. | Handled via authoritative server-derived evaluation; cannot store orphaned facts. |
| **15** | **Reward version preserved** | Stored under `merchant-reward/v1`. | Contract version string recorded immutably on each memory row. |
| **16** | **Contribution-formula version preserved** | Stored under `contribution-formula/v1`. | Formula version recorded immutably on each memory row. |
| **17** | **Reordered database results** | SQL results returned in arbitrary internal order. | Query layer strictly enforces `ORDER BY observed_at DESC, id ASC`. |
| **18** | **Pagination consistency** | Paginating across large result sets. | Non-overlapping, deterministic pages via `limit` and `offset`. |
| **19** | **Historical policy version immutability** | Upgrading policy version in merchant catalog. | Existing historical records retain their original `policy_version`. |
| **20** | **Concurrent duplicate insertion** | Database race condition on identical observation. | Unique index on `idempotency_key` guarantees exactly one insert succeeds. |
| **21** | **Client attempts to inject fake reward** | API payload attempting to supply reward contribution. | `RecordMemoryRequest` schema strictly forbids client-supplied rewards. |
| **22** | **Client attempts to inject eligibility** | API payload attempting to override `learning_eligible`. | `RecordMemoryRequest` schema strictly forbids client-supplied eligibility. |
| **23** | **Post-outcome mutating pre-decision context** | Realized outcome attempting to alter intent key. | `buyer_context_key` remains strictly isolated from transaction figures. |
| **24** | **Aggregation across mixed contexts** | Policy evaluated across multi-category populations. | Summary accurately aggregates totals without context collapse. |
| **25** | **Static AST Boundary Audit** | Inspection of `services/memory/` for forbidden learning terms. | AST audit confirms zero bandits, zero RL, zero policy updates. |
