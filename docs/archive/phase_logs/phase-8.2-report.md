# Phase 8.2 Refinement Report: Post-Freeze Semantic Hardening

**Project**: Merchant Policy Agent (Razorpay AI Buildathon 2026 — Track 01)  
**Phase**: Phase 8.2 — Reward / Objective Definition: Post-Freeze Semantic Hardening  
**Status**: **COMPLETE, VERIFIED, ADVERSARIALLY HARDENED, CONTRACT FROZEN (`merchant-reward/v1`, `contribution-formula/v1`), NO LEARNING ALGORITHM IMPLEMENTED, PHASE 8.3 NOT STARTED.**  
**Core Invariant Preserved**: **OPTIMIZATION UNIT IS THE ELIGIBLE AI-BUYER OPPORTUNITY; DENOMINATOR IS NOT MERELY SUCCESSFUL PURCHASES; UNSAFE OPPORTUNITIES CANNOT VANISH TO ARTIFICIALLY INFLATE REWARD**  
**Hard Stop Condition**: **Strictly Honored**. Phase 8.3 has **NOT** been started.

---

## 1. Status

**COMPLETE & CONTRACT FROZEN**. All targeted semantic audits and hardening items have been implemented, verified, and integrated into the test suite. 421/421 regression tests pass with 100% success.

---

## 2. Guardrail-Failure Conclusion (Refinement A)

- **Issue Discovered**: Previously, outcomes with `GUARDRAIL_FAILURE` were marked `is_admissible = False` and excluded from the aggregator's denominator. In a population of 100 opportunities with 20 guardrail failures and 10 conversions (yielding ₹8,000 total contribution), removing the 20 failures shrank the denominator to 80, artificially inflating average contribution from ₹80 to ₹100 per shopper.
- **Conclusive Treatment**:
  - Guardrail failures belong in the denominator with **0 contribution** (`REWARD_GUARDRAIL_VIOLATION`), ensuring the policy is properly penalized for failing to produce safe commercial value.
  - The opportunity is explicitly flagged with `is_safety_violation = True`.
  - In `AggregatedRewardObjective`, `guardrail_violation_count` is tracked and `is_policy_admissible = False` is enforced if any violation occurred.
  - This prevents any policy from improving its measured economic performance by converting undesirable opportunities into denominator exclusions.
  - Meanwhile, corrupted data (`REWARD_INVALID`) and missing inputs (`REWARD_DATA_UNAVAILABLE`) remain excluded from denominator (`is_admissible = False`).

---

## 3. Realized-Revenue Conclusion (Refinement B)

- **Formula Verification**:
  $$\text{RealizedRevenue}_i = \text{BaselineCatalogRevenue}_i - \text{MerchantFundedDiscount}_i$$
  is verified across the complete execution path:
  1. Phase 2: `domain/economics.py` defines `net_revenue = baseline_revenue - promotional_discount`.
  2. Phase 4: `CandidateEconomics` defines `net_offered_price_paise`.
  3. Phase 5: `ExecutionGate` recalculates inventory prices and authorizes `recalculated_economics.net_revenue_paise`.
  4. Webhook: Razorpay `payment.captured` captures the exact authorized net price in paise.
  5. Phase 8.1: `PolicyLearningEvidence.observed_revenue_paise` records this verified transaction cash inflow.
- **Authoritative Economic Boundary**:
  $$\text{ModeledGrossContribution}_i = \text{RealizedRevenue}_i - \text{TotalCOGS}_i$$
  represents **merchant modeled gross contribution** under the supported Phase 2 commerce model. It is **not** a complete accounting-profit calculation: corporate taxes, overhead, shipping, and unmodeled gateway processing fees (e.g. MDR) are outside scope and strictly prevented from entering the formula (`extra="forbid"` on schemas).

---

## 4. Opportunity-Identity Conclusion (Refinement C)

The architecture strictly disentangles four distinct identity concepts:
1. **`opportunity_id`**: The canonical decision-instance identifier: `f"{experiment_id}:{scenario_id}:{variant}"`. Uniquely identifies the single evaluation of a policy on a scenario.
2. **`buyer_context_key`**: The deterministic fingerprint of commercial intent (e.g. `bck_travel_backpack_TIER_MID_...`). Multiple distinct opportunities can share the exact same context key without collapsing.
3. **`scenario_id`**: The benchmark test case identifier (e.g. `scen_travel_01`).
4. **`aggregation_key`**: The grouping key for policy performance retrieval: `f"{merchant_id}:{scoped_bck}:{policy_id}:{policy_version}"`. When aggregating across diverse contexts, `scoped_bck` is set to `"ALL_CONTEXTS"`.

---

## 5. Exact Semantic Changes Made

1. **`services/reward/schemas.py`**:
   - Added `REWARD_GUARDRAIL_VIOLATION` to `RewardState` enum.
   - Added `is_safety_violation: bool = False` to `PolicyOpportunityReward`.
   - Added `guardrail_violation_count: int = 0` and `is_policy_admissible: bool = True` to `AggregatedRewardObjective`.
2. **`services/reward/calculator.py`**:
   - Updated `RewardSignalEvaluator.evaluate_opportunity`: Maps `GUARDRAIL_FAILURE` to `REWARD_GUARDRAIL_VIOLATION` with `is_admissible = True`, `is_safety_violation = True`, and `reward_contribution_paise = 0`.
   - Added `is_safety_violation` parameter to `_build_reward`.
   - Documented modeled gross contribution boundary in docstrings.
3. **`services/reward/aggregator.py`**:
   - Updated `ObjectiveAggregator.aggregate_objective`: Computes `guardrail_violation_count` and `is_policy_admissible = (guardrail_violation_count == 0)`.
   - Disentangles `buyer_context_key` across multi-scenario populations, assigning `"ALL_CONTEXTS"` when contexts are mixed.

---

## 6. Contracts Changed

- **`merchant-reward/v1`**: Backward-compatible non-breaking extension:
  - Added `is_safety_violation` to `PolicyOpportunityReward`.
  - Added `guardrail_violation_count` and `is_policy_admissible` to `AggregatedRewardObjective`.
  - Added `REWARD_GUARDRAIL_VIOLATION` to `RewardState` enum.
- **`contribution-formula/v1`**: Unchanged; exact formula remains `RealizedRevenue - RealizedCOGS`.

---

## 7. Files Changed

| File | Status | Description |
|:---|:---:|:---|
| [`services/reward/schemas.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/reward/schemas.py) | **Modified** | Added safety fields and `REWARD_GUARDRAIL_VIOLATION`. |
| [`services/reward/calculator.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/reward/calculator.py) | **Modified** | Handled guardrail failures in denominator; documented revenue boundaries. |
| [`services/reward/aggregator.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/reward/aggregator.py) | **Modified** | Tracked `guardrail_violation_count`, `is_policy_admissible`, and context scoping. |
| `tests/unit/test_reward_guardrails.py` | **Modified** | Added anti-selection bias 100-opportunity test. |
| `tests/unit/test_reward_calculator.py` | **Modified** | Verified `REWARD_GUARDRAIL_VIOLATION` vs `REWARD_INELIGIBLE`. |
| `tests/integration/test_reward_adversarial.py` | **Modified** | Updated adversarial cases and added 5 new refinement boundary tests. |
| `docs/phase-8.2-*.md` (4 files) | **Modified** | Updated contracts, definitions, adversarial reviews, and report. |
| [`walkthrough.md`](file:///C:/Users/DHANUSH%20A%20G/.gemini/antigravity-ide/brain/965695ea-ba80-4782-97a9-46a29cdc5c64/walkthrough.md) | **Modified** | Updated with refinement results. |

---

## 8. New / Updated Tests

- **`test_guardrail_failures_remain_in_denominator_preventing_selection_bias`**: Proves that 20 guardrail failures in 100 opportunities dilute contribution per shopper from ₹100 to ₹80 and set `is_policy_admissible = False`.
- **`test_reward_signal_evaluator_guardrail_violation_retained`**: Verifies `REWARD_GUARDRAIL_VIOLATION` classification.
- **`test_refinement_guardrail_pre_execution_rejection`**: Verifies Phase 5 pre-execution rejection remains in denominator with 0 contribution.
- **`test_refinement_authoritative_revenue_discount_formula`**: Proves `RealizedRevenue = Baseline - Discount`.
- **`test_refinement_unsupported_accounting_cost_cannot_enter_formula`**: Verifies `extra="forbid"` rejects unauthorized financial metrics.
- **`test_refinement_identity_distinct_opportunities_same_context`**: Proves distinct opportunities sharing the same `buyer_context_key` do NOT collapse.
- **`test_refinement_aggregation_mixed_contexts_population`**: Proves multi-context populations produce `"ALL_CONTEXTS"` aggregation keys.
- **Total Phase 8.2 Tests**: **42 automated tests**.

---

## 9. Full Regression Result: 421/421 Tests Passing (100%)

```text
======================= 421 passed, 1 warning in 7.80s ========================
```

| Phase | Test Suite | Tests | Result |
|:---|:---|:---:|:---:|
| **Phase 1** | Razorpay Test-Mode Foundation, Webhooks, State Machine, Money | 27 | ✅ 27/27 PASSED |
| **Phase 2** | Merchant Commerce Model, Unit Economics, Multi-Tenant Isolation | 29 | ✅ 29/29 PASSED |
| **Phase 3** | Buyer Intent Engine, Normalizer, Golden Intent Suite, Adversarial, Repro | 69 | ✅ 69/69 PASSED |
| **Phase 4** | Schemas, Validator, Ranking, Baseline, Agent, Golden Suite, Hardening | 44 | ✅ 44/44 PASSED |
| **Phase 5** | Execution Schemas, Revalidation, Concurrency, Gate, Security, Real Provider | 28 | ✅ 28/28 PASSED |
| **Phase 6** | Buyer Lab Schemas, Filter, Evaluator, Benchmark (50), API, Security, Repro, Hardening | 85 | ✅ 85/85 PASSED |
| **Phase 7** | Experiment Schemas, Diff, Assignment, Validator, Metrics, Evaluator (MDE), Benchmark (50), API, Security, Repro | 79 | ✅ 79/79 PASSED |
| **Phase 8.1**| Learning Schemas, Context Key, Validator, Immutability, API, Security & AST Audit | 18 | ✅ 18/18 PASSED |
| **Phase 8.2**| Reward Calculator, Schemas, Aggregator, Guardrails, API, 29 Adversarial Modes, AST Audit | 42 | ✅ 42/42 PASSED |
| **Total** | **Complete Suite Across All Phases** | **421** | ✅ **421/421 PASSED (100%)** |
| **Regressions** | | **0** | **None** |

---

## 10. Remaining Limitations

1. **Passive Signal Layer Only**: Phase 8.2 strictly defines the learning objective. It does not store historical policy trajectories or update policy memory (deferred to Phase 8.3).
2. **Production Evidence Unsupported**: Live real-world payments remain unsupported in this buildathon test-mode track.

---

## 11. Explicit Boundary Confirmations

> [!IMPORTANT]
> **Refinement Boundary Confirmations**:
> - **NO** learning algorithm was implemented.
> - **NO** policy memory was implemented.
> - **NO** policy updates were implemented.
> - **NO** exploration/exploitation was implemented.
> - **NO** n8n dependency was introduced.
> - **Phase 8.3 was NOT started.**
> - Static AST boundary audit confirmed zero forbidden learning terms in `services/reward/`.
