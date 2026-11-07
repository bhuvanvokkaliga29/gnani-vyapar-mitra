# Phase 8.3 Completion Report: Merchant Policy Memory & Historical Retrieval

**Project**: Merchant Policy Agent (Razorpay AI Buildathon 2026 — Track 01)  
**Phase**: Phase 8.3 — Merchant Policy Memory & Historical Retrieval  
**Status**: **COMPLETE, VERIFIED, ADVERSARIALLY HARDENED, CONTRACT FROZEN (`merchant-memory/v1`), NO LEARNING ALGORITHM IMPLEMENTED, PHASE 8.4 NOT STARTED.**  
**Core Invariant Preserved**: **HISTORICAL POLICY MEMORY STORES IMMUTABLE FACTS ONLY; NO POLICY RANKING, NO DECISION-MAKING, NO POLICY MUTATION**  
**Hard Stop Condition**: **Strictly Honored**. Phase 8.4 has **NOT** been started.

---

## 1. Status

**COMPLETE & CONTRACT FROZEN**. Phase 8.3 establishes the authoritative merchant-specific historical policy memory layer (`merchant-memory/v1`). 442/442 regression tests pass with 100% success.

---

## 2. Memory Model

The memory model records immutable historical observations traceable across the complete experimental and economic hierarchy:
$$\text{Merchant} \to \text{Policy/Version} \to \text{Opportunity} \to \text{Buyer Context} \to \text{Experiment/Variant} \to \text{Evidence} \to \text{Reward}$$

Each memory record answers:
- Which merchant? (`merchant_id`)
- Which policy & version? (`policy_id`, `policy_version`)
- Which opportunity? (`opportunity_id = f"{experiment_id}:{scenario_id}:{variant}"`)
- Which buyer context? (`buyer_context_key`)
- Which experiment & arm? (`experiment_id`, `variant`)
- What evidence source? (`evidence_source = SIMULATED | TEST_MODE_OBSERVED`)
- Was it learning-eligible? (`learning_eligible = True | False`)
- What reward was calculated? (`reward_id`, `reward_state`, `reward_contribution_paise`)
- What contract and formula versions? (`merchant-reward/v1`, `contribution-formula/v1`)
- Was there a commercial safety violation? (`is_safety_violation = True | False`)
- When did the observation occur? (`observed_at`)

---

## 3. Canonical Identity Model

The architecture strictly distinguishes four distinct identity concepts:
1. **`opportunity_id`**: Canonical decision-instance identifier: `f"{experiment_id}:{scenario_id}:{variant}"`. Uniquely identifies the single evaluation of a policy on a scenario.
2. **`buyer_context_key`**: Deterministic fingerprint of normalized commercial intent (`f"bck_{category}_{tier}_{digest}"`). Multiple distinct opportunities can share the exact same context key without collapsing.
3. **`scenario_id`**: Benchmark or simulation case identifier (e.g. `scen_travel_01`).
4. **`aggregation_key`**: Performance grouping key: `f"{merchant_id}:{scoped_bck}:{policy_id}:{policy_version}"`. When aggregating across diverse contexts, `scoped_bck` is set to `"ALL_CONTEXTS"`.

---

## 4. Persistence Model

- Implemented via `PolicyMemoryRecord` in [`domain/models.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/domain/models.py).
- Relational mapping with foreign keys to `merchants.id`, `experiments.id`, and `learning_evidence.id`.
- Integer paise representation for all financial values (`BigInteger`), eliminating float rounding errors.
- Exact Decimal representation for gross margins (`Numeric(5, 2)`).

---

## 5. Immutability Semantics

- **Append-Only Storage**: Historical facts are written once and never updated or overwritten.
- **Contract Freezing**: Records retain their original `policy_version`, `reward_version`, and `formula_version` permanently.
- **Auditability**: Reconciliation and corrections are represented by new records rather than destructive in-place mutations.

---

## 6. Deduplication & Idempotency Semantics

- Unique constraint and index on `idempotency_key = f"mem_{evidence.evidence_id}"`.
- Replaying the same evidence record returns the existing memory record with zero duplicate rows created.
- Concurrent duplicate writes are safely serialized by database uniqueness.

---

## 7. Retrieval APIs

Exposed via [`apps/api/routers/memory.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/apps/api/routers/memory.py):
- `POST /api/v1/memory/record`: Ingests an evidence ID into memory.
- `GET /api/v1/memory/{memory_id}`: Fetches individual memory record (tenant-scoped).
- `GET /api/v1/memory`: Queries history with filtering (`policy_id`, `buyer_context_key`, `variant`, `source`, `learning_eligible`, time range) and pagination (`limit`, `offset`).
- `GET /api/v1/memory/summary/policy`: Computes factual summary metrics for a policy under a context or merchant-wide.

---

## 8. Aggregation Semantics

The summary endpoint computes **factual aggregations only**:
- `total_opportunities`, `eligible_opportunities`, `ineligible_opportunities`
- `guardrail_violations`, `is_policy_admissible`
- `order_created_count`, `converted_payments`, `conversion_rate`
- `total_realized_revenue_paise`, `total_realized_cogs_paise`, `total_contribution_paise`
- `contribution_per_shopper_paise`, `contribution_per_shopper_decimal`, `average_margin_percent`
- **Strict Boundary**: The aggregation contains **NO recommendations**, **NO policy ranking**, and **NO selection decisions**.

---

## 9. Provenance & Version Preservation

Every record permanently records:
- `memory_version = "merchant-memory/v1"`
- `policy_version = "merchant-policy/v1"`
- `experiment_version = "policy-experiment/v1"`
- `reward_version = "merchant-reward/v1"`
- `formula_version = "contribution-formula/v1"`
- `evidence_source = SIMULATED | TEST_MODE_OBSERVED`

---

## 10. Tenant-Isolation Guarantees

- Database foreign keys and indices enforce tenant scoping.
- Service layer rejects cross-tenant evidence/reward combinations (`MemoryTenantViolationError`).
- Query layer mandates `merchant_id` filter on all queries.
- API endpoints reject cross-tenant access with `403 Forbidden`.

---

## 11. Security Boundary

- **Client Cannot Forge Rewards**: `RecordMemoryRequest` only accepts `evidence_id` and `merchant_id`. The server derives the reward authoritatively via Phase 8.2 logic.
- **Client Cannot Override Eligibility**: `learning_eligible` is loaded strictly from the Phase 8.1 evidence record.
- **Anti-Leakage**: Realized post-decision payment data is never leaked into pre-decision buyer context keys.

---

## 12. Database Indexes

Six dedicated composite indexes defined in `PolicyMemoryRecord`:
1. `ix_policy_memory_merchant_policy`: `(merchant_id, policy_id)`
2. `ix_policy_memory_merchant_policy_ver`: `(merchant_id, policy_id, policy_version)`
3. `ix_policy_memory_merchant_context`: `(merchant_id, buyer_context_key)`
4. `ix_policy_memory_merchant_pol_ctx`: `(merchant_id, policy_id, buyer_context_key)`
5. `ix_policy_memory_merchant_exp`: `(merchant_id, experiment_id)`
6. `ix_policy_memory_merchant_obs_time`: `(merchant_id, observed_at)`

---

## 13. Files & Modules Changed

| File | Status | Description |
|:---|:---:|:---|
| [`domain/models.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/domain/models.py) | **Modified** | Added `PolicyMemoryRecord` table and indexes. |
| [`services/memory/schemas.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/memory/schemas.py) | **New** | Pydantic v2 schemas for `merchant-memory/v1`. |
| [`services/memory/errors.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/memory/errors.py) | **New** | Domain exceptions. |
| [`services/memory/service.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/memory/service.py) | **New** | `PolicyMemoryService` implementation. |
| [`services/memory/__init__.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/memory/__init__.py) | **New** | Module exports. |
| [`apps/api/routers/memory.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/apps/api/routers/memory.py) | **New** | FastAPI router with 4 endpoints. |
| [`apps/api/main.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/apps/api/main.py) | **Modified** | Registered `memory.router`. |
| `tests/unit/test_memory_*.py` (2 files) | **New** | Unit tests for schemas and service. |
| `tests/integration/test_memory_*.py` (2 files) | **New** | API integration tests and 25 adversarial cases. |
| `docs/phase-8.3-*.md` (5 files) | **New** | Formal documentation suite. |

---

## 14. Tests Added

- **Unit Tests**: 6 tests covering schemas, service, idempotency, tenant isolation, and factual summary.
- **Integration Tests**: 15 tests covering API lifecycle, the 25 adversarial failure modes, and static AST boundary audit.
- **Total Tests Added in Phase 8.3**: **21 automated tests**.

---

## 15. Full Regression Result: 442/442 Tests Passing (100%)

```text
======================= 442 passed, 1 warning in 12.42s ========================
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
| **Phase 8.3**| Memory Schemas, Service, API, 25 Adversarial Modes, Static AST Audit | 21 | ✅ 21/21 PASSED |
| **Total** | **Complete Suite Across All Phases** | **442** | ✅ **442/442 PASSED (100%)** |
| **Regressions** | | **0** | **None** |

---

## 16. Adversarial Results

All **25 adversarial failure modes** specified in Step 18 were tested and verified in [`tests/integration/test_memory_adversarial.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/integration/test_memory_adversarial.py):
- Context and opportunity orthogonality verified.
- Deduplication and idempotency verified.
- Cross-tenant access blocked.
- Source taxonomies (`SIMULATED`, `TEST_MODE_OBSERVED`) and economic states (`REWARD_GUARDRAIL_VIOLATION`, negative contribution, zero contribution) preserved.
- Static AST audit confirms zero learning algorithms, bandits, or policy mutation logic in `services/memory/`.

---

## 17. Performance & Limitations

- Relational PostgreSQL/SQLite storage with composite indexing guarantees fast, indexed retrieval on `(merchant_id, policy_id)` and `(merchant_id, buyer_context_key)` without needing external vector or caching infrastructure.
- Passive storage only: Does not actively evaluate or update policies.

---

## 18. Phase 8.4 Handoff Contract

Phase 8.4 will implement the **Autonomous Policy Learning Algorithm**. It is authorized to consume from Phase 8.3:
```text
PolicyMemoryRecord:
  ├── merchant_id
  ├── policy_id & policy_version
  ├── buyer_context_key
  ├── opportunity_id
  ├── experiment_id & variant
  ├── evidence_source & outcome_type
  ├── learning_eligible
  ├── reward_state & is_admissible & is_safety_violation
  ├── realized_revenue_paise & realized_cogs_paise & reward_contribution_paise
  ├── margin_percent
  └── observed_at
```
Using this authoritative historical memory, Phase 8.4 may reason over past policy performance across buyer contexts.

---

## 19. Explicit Boundary Confirmations

> [!IMPORTANT]
> **Boundary Confirmations**:
> - **NO** learning algorithm (bandit, reinforcement learning, policy gradient, Bayesian optimization) was implemented.
> - **NO** policy ranking was implemented.
> - **NO** exploration/exploitation strategies were implemented.
> - **NO** policy mutations or automatic policy updates were implemented.
> - **NO** n8n dependency was introduced.
> - **Phase 8.4 was NOT started.**
> - Static AST boundary audit confirmed zero forbidden learning terms in `services/memory/`.
