# Phase 8.1 Completion Report: Learning Contract & Evidence Model

**Project**: Merchant Policy Agent (Razorpay AI Buildathon 2026 — Track 01)  
**Phase**: Phase 8.1 — Merchant Policy Learning Foundation: Learning Contract & Evidence Model  
**Status**: **COMPLETE, VERIFIED, CONTRACT FROZEN (`merchant-learning/v1`), EVIDENCE LAYER OPERATIONAL, NO LEARNING ALGORITHM IMPLEMENTED, PHASE 8.2 NOT STARTED.**  
**Core Invariant Preserved**: **VALIDATED EXPERIMENT EVIDENCE IS THE STRICT FIREWALL TO AUTONOMOUS LEARNING**

---

## 1. Files Changed and Created

| File | Status | Description |
|:---|:---:|:---|
| [`services/learning/schemas.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/learning/schemas.py) | **New** | Pydantic v2 schemas for `PolicyLearningEvidence` (`merchant-learning/v1`), taxonomy enums, context dimensions, and filter models. |
| [`services/learning/errors.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/learning/errors.py) | **New** | Domain exceptions: `LearningError`, `InvalidEvidenceError`, `CrossTenantLearningError`, `EvidenceImmutabilityError`. |
| [`services/learning/context_key.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/learning/context_key.py) | **New** | `BuyerContextKeyBuilder` constructing deterministic, non-PII commercial context keys. |
| [`services/learning/validator.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/learning/validator.py) | **New** | `LearningEvidenceValidator` enforcing provenance, outcome invariants, and deterministic eligibility. |
| [`services/learning/service.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/learning/service.py) | **New** | `LearningEvidenceService` managing authoritative ingestion, persistence, deduplication, and tenant queries. |
| [`services/learning/__init__.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/learning/__init__.py) | **New** | Module exports. |
| [`domain/models.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/domain/models.py) | **Modified** | Added `LearningEvidenceRecord` SQLAlchemy model for SQLite/PostgreSQL persistence. |
| [`apps/api/routers/learning.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/apps/api/routers/learning.py) | **New** | FastAPI router for querying and authoritatively ingesting learning evidence. |
| [`apps/api/main.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/apps/api/main.py) | **Modified** | Registered `learning.router` in application. |
| [`tests/unit/test_learning_schemas.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/unit/test_learning_schemas.py) | **New** | Unit tests for `merchant-learning/v1` schema and taxonomy validation. |
| [`tests/unit/test_learning_context_key.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/unit/test_learning_context_key.py) | **New** | Unit tests for deterministic key construction and demographic profiling rejection. |
| [`tests/unit/test_learning_validator.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/unit/test_learning_validator.py) | **New** | Unit tests for provenance checks, invariant enforcement, and eligibility derivation. |
| [`tests/unit/test_learning_immutability.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/unit/test_learning_immutability.py) | **New** | Unit tests for deduplication, replay safety, and persistent immutability. |
| [`tests/integration/test_learning_api.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/integration/test_learning_api.py) | **New** | Integration tests for FastAPI endpoints and experiment ingestion. |
| [`tests/integration/test_learning_security.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/integration/test_learning_security.py) | **New** | AST boundary audit, cross-tenant isolation, and zero side-effects verification. |
| `docs/phase-8.1-*.md` (5 files) | **New** | Formal Phase 8.1 documentation suite. |

---

## 2. The `merchant-learning/v1` Contract

- **Specification**: `merchant-learning/v1` (frozen)
- **Primary Schema**: `PolicyLearningEvidence`
- **Scoping**: Strictly scoped to authenticated `merchant_id`.
- **Economic Conventions**:
  - `expected_revenue_paise` & `expected_contribution_paise`: Integer paise.
  - `observed_revenue_paise` & `observed_contribution_paise`: Integer paise (strictly null for simulated evidence).
  - `margin_percent`: Decimal / float rounded to 2 decimal places.

---

## 3. Evidence & Outcome Taxonomy

- **Source Taxonomy**:
  - `SIMULATED`: Generated from offline AI Buyer Lab simulations.
  - `TEST_MODE_OBSERVED`: Generated from Phase 5 Execution Gate traversal into Razorpay Test Mode.
  - `PRODUCTION_OBSERVED`: Defined in taxonomy, but strictly unsupported and forbidden in this track.
- **Outcome Taxonomy**:
  - `SIMULATED_SELECTION`: AI Buyer Lab chose the offer.
  - `NO_SELECTION`: Offer not selected.
  - `ORDER_CREATED`: Test-Mode order created via Phase 5.
  - `PAYMENT_SUCCESS`: Webhook-verified payment.
  - `PAYMENT_FAILURE`: Webhook failure notification.
  - `EXECUTION_REJECTED`: Gate rejected execution.
  - `EXPERIMENT_INCONCLUSIVE`: Sourced from inconclusive experiment arm.
- **Core Invariants Enforced**:
  $$\text{ORDER\_CREATED} \ne \text{PAYMENT\_SUCCESS}$$
  $$\text{SIMULATED\_SELECTION} \ne \text{PAYMENT\_SUCCESS}$$

---

## 4. Deterministic Learning-Eligibility Rules

The LLM has zero authority to declare learning eligibility. It is derived deterministically by `LearningEvidenceValidator`:
$$\text{learning\_eligible} \iff \begin{cases}
\text{evidence\_status} == \text{VALID} \\
\land \quad \text{experiment\_status} == \text{COMPLETED} \\
\land \quad \text{guardrail\_failures} == 0 \\
\land \quad \text{provenance\_complete} == \text{True} \\
\land \quad \text{source} \in \{\text{SIMULATED}, \text{TEST\_MODE\_OBSERVED}\} \\
\land \quad \text{sample\_size} \ge 1
\end{cases}$$

---

## 5. Provenance Model & Buyer Context Key

- **Provenance Linkage**: Every record traces directly to `experiment_id`, `experiment_observation_id`, `policy_id`, `policy_version`, and `scenario_id`.
- **Buyer Context Key (`buyer_context_key`)**:
  - Deterministic SHA-256 hash of normalized category, budget tier, sorted requirement signatures, and preference signatures.
  - Zero demographic profiling: Attempted injection of `age`, `gender`, `income`, `race`, or `religion` raises an immediate `SecurityBoundaryError`.

---

## 6. Security, Boundary Audit & Multi-Tenant Isolation

- **Static AST Boundary Audit**: Automated scan verified **zero occurrences** of learning algorithms, multi-armed bandits, contextual bandits, reward models, or policy optimizers in `services/learning/`.
- **Multi-Tenant Isolation**: Enforced on all database queries (`merchant_id`). Cross-tenant requests fail with HTTP 404 or `CrossTenantLearningError`.
- **Rejection of Client Tampering**: External clients cannot submit fake rewards, fake revenue, or declare eligibility.
- **Passive Invariant**: Ingesting learning evidence produces zero side-effects on live merchant policies or catalog prices.

---

## 7. Immutability & Idempotent Deduplication

- **Unique Idempotency Key**: Stored with database unique index on `idempotency_key = f"evi_{observation.idempotency_key}"`.
- **Replay Safety**: Replaying an observation returns the existing record without duplicate insertion or double-counting.
- **Immutability**: Finalized evidence records cannot be mutated.

---

## 8. Automated Test Suite Matrix: 379/379 Tests Passing

```text
======================= 379 passed, 1 warning in 11.71s ========================
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
| **Total** | **Complete Suite Across All Phases** | **379** | ✅ **379/379 PASSED (100%)** |
| **Regressions** | | **0** | **None** |

---

## 9. Known Limitations

1. **Passive Evidence Layer Only**: Phase 8.1 purposefully does not implement learning algorithms, reward formulas, or policy updates (deferred to later sub-phases).
2. **Production Evidence Unsupported**: Live customer transactions are unavailable and explicitly rejected in this test-mode foundation.

---

## 10. Confirmation of Phase 8.2 Status & Hard Stop

> [!IMPORTANT]
> **Phase 8.1 is COMPLETE, VERIFIED, and CONTRACT FROZEN (`merchant-learning/v1`).**
> - **Phase 8.2 (Reward Definition) has NOT been started.**
> - No contextual bandits, multi-armed bandits, or reinforcement learning have been implemented.
> - No reward formulas or loss functions have been calculated.
> - No policy memory or policy optimization has been introduced.
> - No dashboard or n8n workflows have been added.
> - Execution stopped per the Hard Stop Condition.
