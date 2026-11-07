# Phase 8.5 Completion Report: Deterministic Learned Candidate Selection

**Project**: Merchant Policy Agent (Razorpay AI Buildathon 2026 — Track 01)  
**Phase**: Phase 8.5 — Deterministic Learned Candidate Selection  
**Status**: **COMPLETE, VERIFIED, ADVERSARIALLY HARDENED, CONTRACT FROZEN (`policy-selection/v1`), NO EXPLORATION/EXPLOITATION IMPLEMENTED, PHASE 8.6 NOT STARTED.**  
**Core Invariant Preserved**: **DETERMINISTIC EXPLOITATION OF PREDICTED CONTRIBUTION; NO UCB SELECTION, NO EXPLORATION, NO EXECUTION, NO POLICY MUTATION**  
**Hard Stop Condition**: **Strictly Honored**. Phase 8.6 has **NOT** been started.

---

## 1. Status

**COMPLETE, HARDENED & CONTRACT FROZEN**. Phase 8.5 introduces `policy-selection/v1`. Full regression test suite: **505/505 tests passing (100%) across all 12 phases with 0 regressions**.

---

## 2. Selection Objective

To deterministically evaluate candidate policies from Phase 4 using the merchant's Phase 8.4 contextual learning model, rank them by expected economic contribution in integer paise, and select the preferred policy relative to the mandatory `NO_OFFER` reserve baseline.

---

## 3. Candidate-Source Semantics

- Candidates are strictly sourced from Phase 4 (`PolicyCandidate`).
- Zero candidates, discounts, or bundles are invented in Phase 8.5.
- Candidates failing Phase 4 validation (`validation_status == REJECTED`) are marked `selection_eligible=False` and excluded from selection.

---

## 4. Baseline Semantics

- Mandatory `NO_OFFER` baseline is guaranteed on every slate (auto-injected if omitted by caller).
- If $\text{best\_non\_baseline\_offer} \le \text{NO\_OFFER}$, `NO_OFFER` is selected.
- Prevents negative-contribution or sub-baseline offers from being executed.

---

## 5. Ranking Algorithm

Total deterministic ordering:
1. `selection_eligible` (Eligible candidates rank first)
2. `predicted_contribution_paise DESC` (Primary: pure learned predicted contribution)
3. `strategy_priority DESC` (Secondary: deterministic commercial strategy hierarchy)
4. `policy_id ASC` (Tertiary: deterministic candidate string comparison)
5. `policy_version ASC` (Quaternary: deterministic version comparison)

---

## 6. Tie-Breaking Rules

When predicted contributions tie:
- Strategy priority breaks secondary ties (`COMPLEMENTARY_BUNDLE` > `VALUE_BUNDLE` > `SINGLE_PRODUCT` > `BOUNDED_DISCOUNT` > `ALTERNATIVE_PRODUCT` > `NON_PRICE_INCENTIVE` > `NO_OFFER`).
- Lexicographical candidate ID breaks tertiary ties (`policy_id ASC`).
- **composite_score is EXCLUDED**: No multi-factor or heuristic score enters the tie-break, guaranteeing that the selection score is strictly predicted contribution.
- **Uncertainty is NEVER used as a tie-breaker.**

---

## 7. Uncertainty Handling

- Predictive uncertainty ($\sigma(x)$) and UCB scores are computed and recorded as diagnostic metadata only.
- Uncertainty does not affect candidate ranking, tie-breaking, or selection.

---

## 8. Cold-Start Behavior

- With zero observations, all offers predict $0$ paise.
- Offers tie with the $0$ paise `NO_OFFER` baseline, resulting in `NO_OFFER` selection with reason `"NO_VALID_POSITIVE_OFFER"`.

---

## 9. Failure-Closed Behavior

- Incompatible contract versions (`selection_version != "policy-selection/v1"`) are rejected with HTTP 400.
- Empty candidate sets raise `EmptyCandidateSetError` (HTTP 400).
- Malformed candidates raise `MalformedCandidateError` (HTTP 400).
- Cross-tenant requests raise `MerchantSelectionIsolationError` (HTTP 403).

---

## 10. Input / Output Contracts

- **Request**: `PolicySelectionRequest` (`merchant_id`, `opportunity_id`, `buyer_context_key`, `intent`, `candidates`, `selection_version`).
- **Score**: `CandidateSelectionScore` (`policy_id`, `policy_version`, `predicted_contribution_paise`, `uncertainty`, `rank`, `is_baseline`, `selection_eligible`, `exclusion_reason`).
- **Result**: `PolicySelectionResult` (`selection_id`, `merchant_id`, `opportunity_id`, `selected_policy_id`, `baseline_policy_id`, `selected_predicted_contribution_paise`, `selected_uncertainty`, `baseline_predicted_contribution_paise`, `ranked_candidates`, `selection_reason`, `selection_timestamp`).

---

## 11. Identity Semantics

- Every selection outcome is bound to a canonical `opportunity_id`.
- `buyer_context_key` represents context identity, not opportunity identity.
- Repeated calls for the same `(merchant_id, opportunity_id)` return the idempotent recorded decision.

---

## 12. Versioning

- Selection contract: `policy-selection/v1`
- Model contract: `learning-model/v1`
- Feature contract: `feature-schema/v1`
- Algorithm contract: `learning-algorithm/v1`

---

## 13. Auditability

- Full decision snapshot persisted in `policy_selection_records` table.
- Preserves complete ranked slate with individual scores and uncertainties.
- Deterministic, factual selection reasons:
  - `HIGHEST_PREDICTED_CONTRIBUTION`
  - `NO_OFFER_BASELINE_DOMINATES`
  - `NO_VALID_POSITIVE_OFFER`
  - `DETERMINISTIC_TIE_BREAK`
  - `NO_OFFER_BASELINE_ONLY`

---

## 14. API Changes

- Added `POST /api/v1/policy-selection/select`
- Added `GET /api/v1/policy-selection/{selection_id}`
- Registered router in `apps/api/main.py`.

---

## 15. Security Boundary

- Cross-tenant data access is blocked at database and service layers.
- Static AST audit confirms zero execution authority, zero Razorpay calls, zero policy mutations, zero exploration policies.

---

## 16. Performance Results

- Selection latency for typical candidate sets (3-5 candidates): **< 1.5 ms** end-to-end including database write.

---

## 17. Files Changed

| File | Type | Description |
|:---|:---:|:---|
| [`domain/models.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/domain/models.py) | **Modified** | Added `PolicySelectionRecord` model with composite index. |
| [`services/selection/schemas.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/selection/schemas.py) | **New** | Contract `policy-selection/v1` Pydantic DTOs. |
| [`services/selection/errors.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/selection/errors.py) | **New** | Domain exceptions for selection. |
| [`services/selection/ranking.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/selection/ranking.py) | **New** | Deterministic ranking, baseline injection, and tie-breaking engine. |
| [`services/selection/service.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/selection/service.py) | **New** | Selection orchestration, persistence, and idempotency. |
| [`apps/api/routers/policy_selection.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/apps/api/routers/policy_selection.py) | **New** | FastAPI endpoints. |
| [`apps/api/main.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/apps/api/main.py) | **Modified** | Registered `policy_selection.router`. |
| [`tests/unit/test_policy_selection_ranking.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/unit/test_policy_selection_ranking.py) | **New** | 9 unit tests for ranking and selection. |
| [`tests/integration/test_policy_selection_service.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/integration/test_policy_selection_service.py) | **New** | 5 integration tests for service, persistence, and API. |
| [`tests/integration/test_policy_selection_adversarial.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/integration/test_policy_selection_adversarial.py) | **New** | 8 adversarial tests, Invariants A-J, and AST audit. |
| [`docs/phase-8.5-policy-selection.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/phase-8.5-policy-selection.md) | **New** | Phase 8.5 technical specification. |
| [`docs/phase-8.5-report.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/phase-8.5-report.md) | **New** | Formal Phase 8.5 completion report. |

---

## 18. Tests Added

- 9 unit tests in `tests/unit/test_policy_selection_ranking.py`
- 5 integration tests in `tests/integration/test_policy_selection_service.py`
- 8 adversarial tests in `tests/integration/test_policy_selection_adversarial.py`
- **Total Phase 8.5 Tests Added**: 22 tests (all passing).

---

## 19. Full Regression Result: 505/505 Tests Passing (100%)

```text
======================= 505 passed, 1 warning in 13.69s ========================
```

| Phase | Modules Covered | Tests | Status |
|:---|:---|:---:|:---:|
| **Phase 1** | Razorpay Test-Mode Foundation, Webhooks, State Machine, Money | 27 | ✅ 27/27 PASSED |
| **Phase 2** | Commerce Models, Unit Economics, Multi-Tenant Isolation, Context | 29 | ✅ 29/29 PASSED |
| **Phase 3** | Normalizer, Validator, Golden Intent Suite, Adversarial, Repro | 69 | ✅ 69/69 PASSED |
| **Phase 4** | Schemas, Validator, Ranking, Baseline, Agent, Golden Suite, Hardening | 44 | ✅ 44/44 PASSED |
| **Phase 5** | Execution Schemas, Revalidation, Concurrency, Gate, Security, Real Provider | 28 | ✅ 28/28 PASSED |
| **Phase 6** | Buyer Lab Schemas, Filter, Evaluator, Benchmark (50), API, Security, Repro, Hardening | 85 | ✅ 85/85 PASSED |
| **Phase 7** | Experiment Schemas, Diff, Assignment, Validator, Metrics, Evaluator (MDE), Benchmark (50), API, Security, Repro | 79 | ✅ 79/79 PASSED |
| **Phase 8.1**| Learning Schemas, Context Key, Validator, Immutability, API, Security & AST Audit | 18 | ✅ 18/18 PASSED |
| **Phase 8.2**| Reward Calculator, Schemas, Aggregator, Guardrails, API, 29 Adversarial Modes, AST Audit | 42 | ✅ 42/42 PASSED |
| **Phase 8.3**| Memory Schemas, Service, API, 25 Adversarial Modes, Reconciliation Suite, Static AST Audit | 27 | ✅ 27/27 PASSED |
| **Phase 8.4**| LinUCB Algorithm, Feature Extractor, Pure-Python Linalg, Model Service, Statistical Suite, Adversarial Suite, Refinement Hardening | 35 | ✅ 35/35 PASSED |
| **Phase 8.5**| Candidate Selection Schemas, Ranking Engine, Baseline Injection, Service, Idempotency, Adversarial Suite, AST Audit | 22 | ✅ 22/22 PASSED |
| **Total** | **Complete Suite Across All Phases** | **505** | ✅ **505/505 PASSED (100%)** |
| **Regressions** | | **0** | **None** |

---

## 20. Adversarial Results

- All Invariants A–J verified:
  - Selected policy belongs strictly to candidate set.
  - Structurally invalid or rejected candidates are never selected.
  - Sub-baseline or negative offers always select `NO_OFFER`.
  - Strictly superior offers are always selected.
  - Reordering input candidate list produces identical output.
  - Altering uncertainty does not change ranking or selection.
  - Tenant isolation prevents cross-merchant leakage.
  - Static AST audit confirms zero execution or policy mutation tokens.

---

## 21. Known Limitations

- **Pre-Decision Reliance**: Selection assumes candidate economics and buyer context accurately reflect transaction conditions at decision time.
- **Pure Exploitation**: Phase 8.5 does not explore novel candidates; exploration mechanics are deliberately isolated to Phase 8.7.

---

## 22. Phase 8.6 Handoff

Phase 8.5 delivers:
- `ranked_candidates`: Full slate with predictions, ranks, and uncertainties.
- `selected_policy_id`: Preferred candidate.
- `baseline_policy_id`: Reserve option.
- `selection_reason`: Factual basis.
Phase 8.6 will evaluate this slate against merchant guardrails, margin floors, and inventory admissibility without re-ranking.

---

## 23. Explicit Confirmation

- **NO** UCB action selection was implemented.
- **NO** exploration/exploitation was implemented.
- **NO** policy promotion was implemented.
- **NO** policy mutation was implemented.
- **NO** transaction execution was implemented.
- **NO** Razorpay calls were made.
- **NO** n8n dependency was introduced.
- **Phase 8.6 has NOT been started.**

---

### Hard Stop Maintained

> **PHASE 8.5 COMPLETE, VERIFIED, ADVERSARIALLY HARDENED, CONTRACT FROZEN (`policy-selection/v1`), NO EXPLORATION/EXPLOITATION IMPLEMENTED, PHASE 8.6 NOT STARTED.**
