# Phase 7 Completion Report: Controlled Policy Experiments

**Project**: Merchant Policy Agent (Razorpay AI Buildathon 2026 — Track 01)  
**Phase**: Phase 7 — Controlled Policy Experiments for Merchant Policy Performance  
**Status**: **COMPLETE, VERIFIED, BENCHMARK CERTIFIED, CONTRACT FROZEN (`policy-experiment/v1`)**  
**Core Invariant Preserved**: **SIMULATED BUYER SELECTION $\ne$ REAL CUSTOMER CONVERSION**  
**Hard Stop Condition**: Maintained. Phase 8 has **NOT** been started.

---

## 1. Key Refinements & Methodological Hardening

In response to rigorous methodological review, four critical architectural enhancements were executed:

### A. "Controlled Policy Experimentation" Language Precision
- **Resolution**: Replaced over-reaching "causal" claims with **"controlled policy experimentation"**.
- **Experimental Unit**: Formally defined as the individual **buyer decision instance / scenario opportunity**.
- **Assignment Population**: Explicitly bounded to a closed set of `BuyerIntent` specifications, budget bounds, and synthetic competitor fixtures.
- **Interference & Non-Contamination**: Proved zero cross-contamination between arms; Control buyers never receive treatment incentives; merchant internal financials remain strictly isolated from the buyer layer.
- **Axiom Enforced**: A controlled randomized comparison over simulated scenarios demonstrates relative empirical performance under test conditions, but does not claim unconditional real-world causal certainty.

### B. Observed Allocation Reporting (Approximate Balance)
- **Resolution**: Eliminated naive claims of an "exact 50/50" split. Finite hash allocation produces an approximately balanced allocation (e.g. 24 vs 26 out of 50).
- **Audit Metrics Added**:
  - `actual_control_count`: Exact number of instances assigned to Control.
  - `actual_treatment_count`: Exact number of instances assigned to Treatment.
  - `allocation_ratio`: Observed treatment-to-control ratio ($\frac{\text{treatment\_count}}{\text{control\_count}}$).

### C. Multidimensional Evidence Evaluation (Beyond Simplistic Zero Delta)
- **Resolution**: Replaced the simplistic `delta == 0` check with an integrated four-factor statistical evaluation:
  1. **Sample Size**: If $N < 10$ or an arm is empty $\to$ `INSUFFICIENT_SAMPLE`.
  2. **Guardrail Compliance**: If Treatment breaches margin floors or discount limits $\to$ `GUARDRAIL_FAILURE` (winner is `CONTROL`).
  3. **Effect Size & Minimum Detectable Effect (MDE)**:
     - If absolute delta is zero $\to$ `INCONCLUSIVE`.
     - If relative difference is below MDE noise threshold ($|\Delta_{\text{rel}}| < 2.0\%$, e.g. 50.0% vs 50.1%) $\to$ `INCONCLUSIVE` (winner is `None`).
  4. **Directional Superiority**: Treatment wins only when outperforming Control by $> \text{MDE}$ while satisfying all guardrails.
- **Five Mutually Exclusive Outcomes**: `CONTROL`, `TREATMENT`, `INCONCLUSIVE`, `INSUFFICIENT_SAMPLE`, `GUARDRAIL_FAILURE`.

### D. Assigned Variant Execution (Selection Bias Prevention)
- **Resolution**: Corrected the architectural sequence to eliminate premature winner execution:
  - During the experiment, each decision instance is assigned to an arm (Control or Treatment).
  - If the simulated buyer selects that merchant offer, the system executes that **assigned variant** through Phase 5 Execution Gate.
  - Winner evaluation is strictly performed **post-hoc** by `ExperimentEvaluator` after all observations are recorded.

---

## 2. Controlled Experiment Architecture

```text
PolicyProposal (Control)    PolicyProposal (Treatment)
          │                               │
          └───────────────┬───────────────┘
                          ▼
                   PolicyDiffEngine
                          ▼
                 PolicyExperiment v1
                          ▼
                 AssignmentEngine (SHA-256)
                          ▼
        ┌─────────────────┴─────────────────┐
        ▼                                   ▼
Control Arm (Assigned)              Treatment Arm (Assigned)
[Approx. Balanced Allocation]       [Approx. Balanced Allocation]
        │                                   │
        ├─────────────────┬─────────────────┤
        ▼                                   ▼
AI Buyer Lab (Phase 6)              AI Buyer Lab (Phase 6)
        │                                   │
[If Selected & Test Mode Enabled]   [If Selected & Test Mode Enabled]
Execute Assigned Variant            Execute Assigned Variant
(via Phase 5 Execution Gate)        (via Phase 5 Execution Gate)
        │                                   │
Razorpay Test Mode Order            Razorpay Test Mode Order
        │                                   │
        └─────────────────┬─────────────────┘
                          ▼
                ExperimentMetricEngine
               (Deterministic Formulas)
                          ▼
                ExperimentEvaluator
    (Effect Size + Sample Size + Uncertainty/MDE + Guardrails)
                          ▼
                 ExperimentResult v1
```

---

## 3. Files Changed and Created

| File | Status | Description |
|:---|:---:|:---|
| [`services/experiments/schemas.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/experiments/schemas.py) | **Modified** | Added `actual_control_count`, `actual_treatment_count`, `allocation_ratio`, `min_detectable_effect`, and assigned variant wording. |
| [`services/experiments/evaluator.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/experiments/evaluator.py) | **Modified** | Implemented MDE threshold evaluation, actual allocation calculation, and 5 classification outcomes. |
| [`services/experiments/runner.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/experiments/runner.py) | **Modified** | Clarified assigned variant execution and eliminated premature winner phrasing. |
| [`services/experiments/__init__.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/experiments/__init__.py) | **Modified** | Softened causal language to controlled policy experimentation. |
| [`services/experiments/diff.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/experiments/diff.py) | **New** | `PolicyDiffEngine` isolating price, bundle, warranty, and margin differences. |
| [`services/experiments/assignment.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/experiments/assignment.py) | **New** | `AssignmentEngine` executing deterministic SHA-256 allocation with seed preservation. |
| [`services/experiments/validator.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/experiments/validator.py) | **New** | `ExperimentValidator` for pre-flight readiness, state transitions, and immutability. |
| [`services/experiments/metrics.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/experiments/metrics.py) | **New** | `ExperimentMetricEngine` computing sample sizes, selection rates, contribution, AOV, and guardrails. |
| [`services/experiments/service.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/experiments/service.py) | **New** | `ExperimentService` managing lifecycle transitions and SQLite/PostgreSQL persistence. |
| [`services/experiments/benchmark.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/experiments/benchmark.py) | **New** | 50-scenario golden experiment benchmark suite. |
| [`domain/models.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/domain/models.py) | **Modified** | Added SQLAlchemy models `ExperimentRecord` and `ObservationRecord`. |
| [`apps/api/routers/experiments.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/apps/api/routers/experiments.py) | **New** | FastAPI router for experiment lifecycle, execution, and metric retrieval. |
| [`apps/api/main.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/apps/api/main.py) | **Modified** | Registered `experiments.router` in application. |
| [`tests/unit/test_experiment_evaluator.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/unit/test_experiment_evaluator.py) | **Modified** | Added tests for MDE noise classification and actual allocation counts/ratio. |
| `tests/unit/test_experiment_*.py` (5 other files) | **New** | Unit test suites for schemas, diff, assignment, validator, metrics, and benchmark. |
| `tests/integration/test_experiment_*.py` (3 files) | **New** | Integration suites for API, security/boundaries, and 10x reproducibility. |
| `docs/phase-7-*.md` (7 files) | **New / Modified** | Comprehensive formal documentation suite. |

---

## 4. N8N Architectural Decision

> [!IMPORTANT]
> **n8n Decision**:
> n8n was evaluated as an optional workflow-orchestration technology but was **not introduced** because Phase 7's authoritative experiment state machine, deterministic assignment, metric calculation, financial integrity, and audit logging are already handled more safely, transparently, and deterministically inside the Python application.

---

## 5. 50-Scenario Golden Benchmark Suite Results

All 50 scenarios in [`services/experiments/benchmark.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/experiments/benchmark.py) execute deterministically with 100% precision:

- Category A: Baseline Comparisons (10/10 PASS)
- Category B: Guardrail Failures (8/8 PASS)
- Category C: Statistical Boundaries & Small Samples (8/8 PASS)
- Category D: Assignment Determinism (8/8 PASS)
- Category E: Integrity & Isolation (8/8 PASS)
- Category F: Test Mode Integration (8/8 PASS)
- **Total Benchmark Compliance**: **50/50 (100.0%)**

---

## 6. Automated Test Suite Matrix: 361/361 Tests Passing

```text
======================= 361 passed, 1 warning in 8.98s ========================
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
| **Total** | **Complete Suite Across All 7 Phases** | **361** | ✅ **361/361 PASSED (100%)** |
| **Regressions** | | **0** | **None** |

---

## 7. Confirmation of Hard Stop Condition

> [!IMPORTANT]
> **Phase 7 is COMPLETE, METHODOLOGICALLY REFINED, VERIFIED, and CONTRACT FROZEN (`policy-experiment/v1`).**
> - **Phase 8 (Autonomous Commercial Policy Learning) has NOT been started.**
> - No multi-armed bandits, reward models, or parameter learning have been added.
> - No autonomous policy updates or reinforcement learning have been introduced.
> - No dashboard or n8n workflows have been introduced.
> - Execution stopped per the Hard Stop Condition.
